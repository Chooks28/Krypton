<?php

namespace Core;

use PhpParser\Node;
use PhpParser\NodeVisitorAbstract;

class RouteVisitor extends NodeVisitorAbstract
{
    protected array $routes = [];

    protected function addRoute(string $namespace, string $route, string $methods)
    {
        $this->routes[] = [
            'namespace' => $namespace,
            'route' => $route,
            'methods' => $methods,
        ];
    }

    protected function resolveValue(Node $node): string
    {
        if ($node instanceof Node\Scalar\String_) {
            return $node->value;
        }

        // Add more types if needed
        return '';
    }

    public function getRoutes(): array
    {
        return $this->routes;
    }

    //  DO NOT declare this abstract — it's already defined in NodeVisitorAbstract
    public function enterNode(Node $node)
    {
        // Optionally provide a base implementation or leave it empty
    }
}

