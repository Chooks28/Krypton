<?php

namespace CMS\WordPress;

use PhpParser\Parser;
use PhpParser\NodeTraverser;
use Core\BaseExtractor;
use CMS\WordPress\GlobalRestRouteVisitor;

class WordPressExtractor
{
    private Parser $parser;
    private array $directories;

    public function __construct(Parser $parser, array $directories)
    {
        $this->parser = $parser;
        $this->directories = $directories;
    }

    public function run(): array
    {
        $allAst = [];
        $phpFiles = $this->findPhpFiles($this->directories);

        foreach ($phpFiles as $file) {
            try {
                $code = file_get_contents($file);
                $ast = $this->parser->parse($code);
                if ($ast !== null) {
                    // Merge top-level AST nodes from all files
                    $allAst = array_merge($allAst, $ast);
                }
            } catch (\Throwable $e) {
                // Ignore parse errors or read errors per file
                continue;
            }
        }

        // === Existing visitors ===
        $directRouteVisitor = new WordPressRouteVisitor();
        $methodCollector = new ClassMethodCollector();
        $varTracker = new VariableAssignmentTracker();
        $restApiHookVisitor = new RestApiInitVisitor();

        $traverser = new NodeTraverser();
        $traverser->addVisitor($directRouteVisitor);
        $traverser->addVisitor($methodCollector);
        $traverser->addVisitor($varTracker);
        $traverser->addVisitor($restApiHookVisitor);
        $traverser->traverse($allAst);

        // === Callback Resolver ===
        $resolver = new CallbackResolver(
            $this->parser,
            $allAst,
            $methodCollector,
            $varTracker
        );

        $resolvedRoutes = [];
        foreach ($restApiHookVisitor->getCallbacks() as $callback) {
            try {
                $resolvedRoutes = array_merge(
                    $resolvedRoutes,
                    $resolver->resolveCallback($callback)
                );
            } catch (\Throwable $e) {
                // Ignore bad callbacks
                continue;
            }
        }

        // === NEW: Global visitor to catch any register_rest_route calls anywhere ===
        $globalRestRouteVisitor = new GlobalRestRouteVisitor();
        $traverserGlobal = new NodeTraverser();
        $traverserGlobal->addVisitor($globalRestRouteVisitor);
        $traverserGlobal->traverse($allAst);

        $globalRoutes = $globalRestRouteVisitor->getRoutes();

        // Combine routes found directly, resolved, and globally detected
        return array_merge(
            $directRouteVisitor->getRoutes(),
            $resolvedRoutes,
            $globalRoutes
        );
    }

    private function findPhpFiles(array $directories): array
    {
        $files = [];

        foreach ($directories as $dir) {
            if (!is_dir($dir)) continue;

            $rii = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir));
            foreach ($rii as $file) {
                if ($file->isFile() && str_ends_with($file->getFilename(), '.php')) {
                    $files[] = $file->getPathname();
                }
            }
        }

        return $files;
    }
}

