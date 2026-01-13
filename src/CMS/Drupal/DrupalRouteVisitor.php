<?php

namespace CMS;

use Core\RouteVisitor;
use PhpParser\Node;
use PhpParser\Node\Expr\New_;
use PhpParser\Node\Expr\MethodCall;
use PhpParser\Node\Scalar\String_;

class DrupalRouteVisitor extends RouteVisitor
{
    private array $routes = [];

    public function enterNode(Node $node)
    {
        if (
            $node instanceof MethodCall &&
            $node->name instanceof Node\Identifier &&
            $node->name->toString() === 'add' &&
            count($node->args) >= 2
        ) {
            $routeNameNode = $node->args[0]->value;
            $routeObjNode = $node->args[1]->value;

            if (
                $routeNameNode instanceof String_ &&
                $routeObjNode instanceof New_ &&
                $routeObjNode->class instanceof Node\Name &&
                $routeObjNode->class->toString() === 'Route'
            ) {
                $this->routes[] = [
                    'route_name' => $routeNameNode->value,
                    'type' => 'addRoute',
                ];
            }
        }
    }

    public function getRoutes(): array
    {
        return $this->routes;
    }
}

