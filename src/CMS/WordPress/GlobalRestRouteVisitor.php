<?php

namespace CMS\WordPress;

use PhpParser\Node;
use PhpParser\NodeVisitorAbstract;
use PhpParser\Node\Expr\Array_;
use PhpParser\Node\Expr\FuncCall;
use PhpParser\Node\Expr\ClassConstFetch;
use PhpParser\Node\Scalar\String_;
use CMS\WordPress\RouteVisitorHelpers;

class GlobalRestRouteVisitor extends NodeVisitorAbstract
{
    use RouteVisitorHelpers;

    private array $routes = [];

    public function enterNode(Node $node)
    {
        // Look for register_rest_route() calls
        if ($node instanceof FuncCall &&
            $node->name instanceof Node\Name &&
            $node->name->toString() === 'register_rest_route') {

            $args = $node->args;
            if (count($args) < 2) return;

            $namespace = $this->resolveValue($args[0]->value);
            $routeRaw = $this->resolveValue($args[1]->value);

            if (!is_string($namespace) || !is_string($routeRaw)) return;

            $route = $this->normalizeRoute($routeRaw);
            $methods = ['GET', 'POST', 'PUT', 'DELETE']; // Default fallback

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
                                $resolved = $this->resolveValue($methodItem->value);
                                if (is_string($resolved)) {
                                    $methods[] = strtoupper($resolved);
                                }
                            }
                        } elseif ($val instanceof ClassConstFetch) {
                            $resolved = $this->resolveConstant($val);
                            if (is_array($resolved)) {
                                $methods = array_merge($methods, $resolved);
                            } elseif (is_string($resolved)) {
                                $methods[] = strtoupper($resolved);
                            }
                        } else {
                            $resolved = $this->resolveValue($val);
                            if (is_string($resolved)) {
                                $methods[] = strtoupper($resolved);
                            }
                        }
                    }
                }
            }

            foreach ($methods as $method) {
                $this->routes[] = [
                    'namespace' => $namespace,
                    'route' => $route,
                    'method' => $method
                ];
            }
        }
    }

    public function getRoutes(): array
    {
        return $this->routes;
    }

    private function normalizeRoute(string $route): string
    {
        // Convert regex-style routes to OpenAPI-style
        return preg_replace('/\(\?P<(\w+)>[^)]+\)/', '{$1}', $route);
    }

    private function resolveValue($node)
    {
        if ($node instanceof String_) {
            return $node->value;
        }

        if ($node instanceof ClassConstFetch) {
            $resolved = $this->resolveConstant($node);
            if (is_string($resolved)) {
                return $resolved;
            }
        }

        return null;
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
        return $constants[$key] ?? null;
    }
}

