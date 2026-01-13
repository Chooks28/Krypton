<?php

namespace CMS\WordPress;

use PhpParser\Node;
use PhpParser\NodeVisitorAbstract;

class VariableAssignmentTracker extends NodeVisitorAbstract
{
    public array $assignments = [];

    public function enterNode(Node $node)
    {
        // Look for: $var = new ClassName();
        if ($node instanceof Node\Expr\Assign) {
            $var = $node->var;
            $expr = $node->expr;

            if ($var instanceof Node\Expr\Variable && is_string($var->name)) {
                $varName = $var->name;

                if ($expr instanceof Node\Expr\New_ && $expr->class instanceof Node\Name) {
                    $className = $expr->class->toString();
                    $this->assignments[$varName] = $className;
                }
            }
        }
    }

    /**
     * Get class name assigned to a given variable (if known).
     */
    public function resolveVariable(string $varName): ?string
    {
        return $this->assignments[$varName] ?? null;
    }
}

