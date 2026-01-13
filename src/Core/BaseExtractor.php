<?php

namespace Core;

use RecursiveIteratorIterator;
use RecursiveDirectoryIterator;

abstract class BaseExtractor
{
    protected $parser;
    protected $directories;

    /**
     * @param \PhpParser\Parser $parser
     * @param string[] $directories
     */
    public function __construct($parser, array $directories)
    {
        $this->parser = $parser;
        $this->directories = $directories;
    }

    protected function findPHPFiles(string $directory): array
    {
        $rii = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($directory));
        $files = [];

        foreach ($rii as $file) {
            if (!$file->isDir() && strtolower($file->getExtension()) === 'php') {
                $files[] = $file->getPathname();
                
            }
        }

        return $files;
    }

    abstract public function run(): array;
}

