<?php

namespace CMS\WordPress;

use PhpParser\Node;
use PhpParser\NodeFinder;
use PhpParser\Parser;
use PhpParser\Node\Expr;
use PhpParser\Node\Stmt;
use PhpParser\NodeTraverser;

class CallbackResolver
{
    private Parser $parser;
    private array $astFiles;
    private ClassMethodCollector $classMethodCollector;
    private VariableAssignmentTracker $assignmentTracker;
    private NodeFinder $nodeFinder;

    public function __construct(
        Parser $parser,
        array $astFiles,
        ClassMethodCollector $classMethodCollector,
        VariableAssignmentTracker $assignmentTracker
    ) {
        $this->parser = $parser;
        $this->astFiles = $astFiles;
        $this->classMethodCollector = $classMethodCollector;
        $this->assignmentTracker = $assignmentTracker;
        $this->nodeFinder = new NodeFinder();
    }

    public function resolveCallback(Expr $callback): array
    {
        $routes = [];

        if ($callback instanceof Expr\Closure) {
            $routes = array_merge($routes, $this->scanForRoutes($callback->stmts));
        } elseif ($callback instanceof Node\Scalar\String_) {
            $fn = $this->classMethodCollector->getGlobalFunction($callback->value);
            if ($fn && $fn->stmts) {
                $routes = array_merge($routes, $this->scanForRoutes($fn->stmts));
            }
        } elseif ($callback instanceof Expr\Array_ && count($callback->items) === 2) {
            $objectExpr = $callback->items[0]->value;
            $methodNameNode = $callback->items[1]->value;

            if ($methodNameNode instanceof Node\Scalar\String_) {
                $methodName = $methodNameNode->value;
                $className = $this->assignmentTracker->resolveClassName($objectExpr);
                if ($className) {
                    $method = $this->classMethodCollector->getMethodNode($className, $methodName);
                    if ($method && $method->stmts) {
                        $routes = array_merge($routes, $this->scanForRoutes($method->stmts));
                    }
                }
            }
        }

        return $routes;
    }

    private function scanForRoutes(array $stmts): array
    {
        $found = [];

        foreach ($stmts as $stmt) {
            // Detect: $controller = new ClassName();
            if (
                $stmt instanceof Stmt\Expression &&
                $stmt->expr instanceof Expr\Assign &&
                $stmt->expr->expr instanceof Expr\New_
            ) {
                $varName = $stmt->expr->var instanceof Expr\Variable ? $stmt->expr->var->name : null;
                $className = $stmt->expr->expr->class instanceof Node\Name ? $stmt->expr->expr->class->toString() : null;

                if ($varName && $className) {
                    // Search for method calls like $controller->register_routes()
                    foreach ($stmts as $subStmt) {
                        if (
                            $subStmt instanceof Stmt\Expression &&
                            $subStmt->expr instanceof Expr\MethodCall &&
                            $subStmt->expr->var instanceof Expr\Variable &&
                            $subStmt->expr->var->name === $varName
                        ) {
                            $methodName = $subStmt->expr->name instanceof Node\Identifier ? $subStmt->expr->name->name : null;

                            if ($methodName) {
                                $methodNode = $this->classMethodCollector->getMethodNode($className, $methodName);
                                if ($methodNode && $methodNode->stmts) {
                                    $wrapped = [new Stmt\Namespace_(null, $methodNode->stmts)];
                                    $traverser = new NodeTraverser();
                                    $visitor = new WordPressRouteVisitor();
                                    $traverser->addVisitor($visitor);
                                    $traverser->traverse($wrapped);

                                    $found = array_merge($found, $visitor->getRoutes());
                                }
                            }
                        }
                    }
                }
            }
        }

        return $found;
    }
}

