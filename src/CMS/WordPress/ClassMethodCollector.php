<?php

namespace CMS\WordPress;

use PhpParser\Node;
use PhpParser\NodeVisitorAbstract;

class ClassMethodCollector extends NodeVisitorAbstract {
    public array $classes = [];
    private array $globalFunctions = [];

    private ?string $currentClass = null;

    public function enterNode(Node $node) {
        // Collect class definitions and methods
        if ($node instanceof Node\Stmt\Class_) {
            if ($node->name !== null) { 
                $this->currentClass = $node->name->name;
                $this->classes[$this->currentClass] = [];
            } else {
                $this->currentClass = null;  // anonymous class or no name
            }
        }        

        if ($node instanceof Node\Stmt\ClassMethod && $this->currentClass !== null) {
            if ($node->name !== null) {
                $methodName = $node->name->name;
                $this->classes[$this->currentClass][$methodName] = $node;
            }
        }

        // ✅ Collect global functions (like wpcf7_register_rest_api)
        if ($node instanceof Node\Stmt\Function_) {
            if ($node->name !== null) {
                $funcName = $node->name->name;
                $this->globalFunctions[$funcName] = $node;
            }
        }
    }

    public function leaveNode(Node $node) {
        if ($node instanceof Node\Stmt\Class_) {
            $this->currentClass = null;
        }
    }

    public function getMethodNode(string $className, string $methodName): ?Node {
        return $this->classes[$className][$methodName] ?? null;
    }

    public function getClassMap(): array {
        return $this->classes;
    }

    // ✅ NEW: Return a global function node if collected
    public function getGlobalFunction(string $name): ?Node\Stmt\Function_ {
        return $this->globalFunctions[$name] ?? null;
    }                                                                   
}

