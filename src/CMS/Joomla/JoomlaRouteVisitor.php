<?php

namespace CMS;

use Core\RouteVisitor;
use PhpParser\Node;
use PhpParser\Node\Expr\MethodCall;
use PhpParser\Node\Scalar\String_;

class JoomlaRouteVisitor extends RouteVisitor
{
    private array $routes = [];

    public function enterNode(Node $node)
    {
        if (
            $node instanceof MethodCall &&
            $node->name instanceof Node\Identifier &&
            $node->name->toString() === 'register' &&
            count($node->args) >= 3
        ) {
            $methodNode = $node->args[0]->value;
            $pathNode = $node->args[1]->value;
            $handlerNode = $node->args[2]->value;

            if (
                $methodNode instanceof String_ &&
                $pathNode instanceof String_ &&
                $handlerNode instanceof String_
            ) {
                $this->routes[] = [
                    'method' => strtoupper($methodNode->value),
                    'path' => $pathNode->value,
                    'handler' => $handlerNode->value,
                ];
            }
        }
    }

    public function getRoutes(): array
    {
        return $this->routes;
    }
}

