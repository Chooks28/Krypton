<?php

namespace CMS\WordPress;

use PhpParser\Node;
use PhpParser\Node\Expr\ClassConstFetch;
use PhpParser\Node\Scalar\String_;

trait RouteVisitorHelpers
{
    private function normalizeRoute(string $route): string
    {
        return preg_replace('/\(\?P<(\w+)>[^)]+\)/', '{$1}', $route);
    }

    private function resolveConstant(ClassConstFetch $node): array
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

    private function resolveValue(Node $node): ?string
    {
        if ($node instanceof String_) {
            return $node->value;
        }

        if ($node instanceof ClassConstFetch) {
            $resolved = $this->resolveConstant($node);
            return is_array($resolved) ? implode(',', $resolved) : $resolved;
        }

        return null;
    }
}
