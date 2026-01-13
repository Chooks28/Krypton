<?php

namespace CMS\WordPress;

use PhpParser\Node;
use PhpParser\NodeVisitorAbstract;

class RestApiInitVisitor extends NodeVisitorAbstract
{
    public array $callbacks = [];

    public function enterNode(Node $node)
    {
        if (
            $node instanceof Node\Expr\FuncCall &&
            $node->name instanceof Node\Name &&
            strtolower($node->name->toString()) === 'add_action'
        ) {
            $args = $node->args;

            if (count($args) >= 2) {
                $hook = $args[0]->value;
                $callback = $args[1]->value;

                // Only continue if hook is 'rest_api_init'
                if (
                    $hook instanceof Node\Scalar\String_ &&
                    strtolower($hook->value) === 'rest_api_init'
                ) {
                    $this->callbacks[] = $callback;
                }
            }
        }
    }

    /**
     * Returns collected callbacks for rest_api_init.
     *
     * @return Node\Expr[] list of callback expressions
     */
    public function getCallbacks(): array
    {
        return $this->callbacks;
    }
}

