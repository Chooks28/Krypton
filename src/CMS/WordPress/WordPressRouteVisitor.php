<?php

namespace CMS\WordPress;

use Core\RouteVisitor;
use PhpParser\Node;
use PhpParser\Node\Expr\Array_;
use PhpParser\Node\Expr\Closure;
use PhpParser\Node\Expr\FuncCall;
use PhpParser\Node\Expr\ClassConstFetch;
use PhpParser\Node\Scalar\String_;
use PhpParser\Node\Stmt\Function_;
use PhpParser\Node\Stmt\Class_;
use PhpParser\Node\Stmt\ClassMethod;

class WordPressRouteVisitor extends RouteVisitor
{
    private array $functions = [];
    private array $classMethods = [];
    private ?string $currentClass = null;

    public function enterNode(Node $node)
    {
        // Collect global functions
        if ($node instanceof Function_) {
            $this->functions[$node->name->toString()] = $node;
            return;
        }

        // Track current class
        if ($node instanceof Class_) {
            $this->currentClass = $node->name ? $node->name->toString() : null;
            if ($this->currentClass !== null) {
                $this->classMethods[$this->currentClass] = [];
            }
            return;
        }

        if ($node instanceof ClassMethod && $this->currentClass !== null) {
            $this->classMethods[$this->currentClass][$node->name->toString()] = $node;
            return;
        }

        // Reset current class when leaving
        if (!($node instanceof ClassMethod) && $this->currentClass !== null) {
            $this->currentClass = null;
        }

        // Detect rest_api_init
        if ($node instanceof FuncCall &&
            $node->name instanceof Node\Name &&
            $node->name->toString() === 'add_action' &&
            isset($node->args[0]) &&
            $this->resolveValue($node->args[0]->value) === 'rest_api_init' &&
            isset($node->args[1])
        ) {
            $callbackNode = $node->args[1]->value;

            if ($callbackNode instanceof Closure) {
                foreach ($callbackNode->stmts as $stmt) {
                    $this->enterNode($stmt);
                }
            }

            if ($callbackNode instanceof String_) {
                $functionName = $callbackNode->value;
                if (isset($this->functions[$functionName])) {
                    $this->analyzeStmts($this->functions[$functionName]->stmts);
                }
            }

            if ($callbackNode instanceof Array_ && count($callbackNode->items) >= 2) {
                $classNode = $callbackNode->items[0]->value ?? null;
                $methodNode = $callbackNode->items[1]->value ?? null;

                if ($methodNode instanceof String_) {
                    $methodName = $methodNode->value;
                    if ($classNode instanceof String_) {
                        $className = $classNode->value;
                        if (isset($this->classMethods[$className][$methodName])) {
                            $this->analyzeStmts($this->classMethods[$className][$methodName]->stmts);
                        }
                    }
                }
            }
        }

        // Direct register_rest_route
        if ($node instanceof FuncCall &&
            $node->name instanceof Node\Name &&
            $node->name->toString() === 'register_rest_route') {
            $this->processRegisterRestRoute($node);
        }

        // Detect register_post_type for REST endpoints
        if ($node instanceof FuncCall &&
            $node->name instanceof Node\Name &&
            $node->name->toString() === 'register_post_type' &&
            isset($node->args[0], $node->args[1])
        ) {
            $postType = $this->resolveValue($node->args[0]->value);
            $argsNode = $node->args[1]->value;

            if ($argsNode instanceof Array_) {
                foreach ($argsNode->items as $item) {
                    if ($item && $item->key instanceof String_ && $item->key->value === 'show_in_rest') {
                        $showInRest = $this->resolveValue($item->value);
                        if ($showInRest === '1' || $showInRest === 'true') {
                            // Add default REST endpoints for this post type
                            $this->addRoute('wp/v2', $postType, 'GET');
                            $this->addRoute('wp/v2', $postType . '/{id}', 'GET,POST,PUT,PATCH,DELETE');
                            $this->addRoute('wp/v2', $postType . '/{id}/revisions', 'GET');
                            $this->addRoute($postType . '/{id}/autosaves', 'GET,POST');
                        }
                    }
                }
            }
        }
    }

    private function analyzeStmts(?array $stmts): void
    {
        if (!$stmts) return;
        foreach ($stmts as $stmt) {
            $this->enterNode($stmt);
        }
    }

    private function processRegisterRestRoute(FuncCall $node): void
    {
        $args = $node->args;
        if (count($args) < 2) return;

        $namespace = $this->resolveValue($args[0]->value);
        $route = $this->normalizeRoute($this->resolveValue($args[1]->value));
        if (!$namespace || !$route) return;

        $methods = ['GET', 'POST', 'PUT', 'DELETE'];

        if (isset($args[2]) && $args[2]->value instanceof Array_) {
            foreach ($args[2]->value->items as $item) {
                if (!$item || !$item->key instanceof String_) continue;

                if ($item->key->value === 'methods') {
                    $methods = [];

                    $val = $item->value;
                    if ($val instanceof String_) {
                        $methods[] = strtoupper($val->value);
                    } elseif ($val instanceof Array_) {
                        foreach ($val->items as $methodItem) {
                            $methods[] = strtoupper($this->resolveValue($methodItem->value));
                        }
                    } elseif ($val instanceof ClassConstFetch) {
                        $methods = $this->resolveConstant($val);
                    } else {
                        $methods[] = strtoupper($this->resolveValue($val));
                    }
                }
            }
        }

        foreach ($methods as $method) {
            $this->addRoute($namespace, $route, $method);
        }
    }

    private function normalizeRoute(string $route): string
    {
        return preg_replace('/\(\?P<(\w+)>[^)]+\)/', '{$1}', $route);
    }

    private function resolveConstant(ClassConstFetch $node)
    {
        $constants = [
            'WP_REST_Server::READABLE'   => ['GET'],
            'WP_REST_Server::CREATABLE'  => ['POST'],
            'WP_REST_Server::EDITABLE'   => ['PUT', 'PATCH'],
            'WP_REST_Server::DELETABLE'  => ['DELETE'],
            'WP_REST_Server::ALLMETHODS' => ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
        ];

        $key = $node->class->toString() . '::' . $node->name->toString();
        return $constants[$key] ?? ['GET'];
    }
}

