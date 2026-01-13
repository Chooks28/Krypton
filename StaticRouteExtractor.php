<?php

require 'vendor/autoload.php';

use PhpParser\ParserFactory;
use CMS\WordPress\WordPressExtractor;
use CMS\Drupal\DrupalExtractor;
use CMS\Joomla\JoomlaExtractor;
use Src\CMSDetector;

class StaticRouteExtractor
{
    private $parser;
    private $directories;
    private $outputFile;

    public function __construct(array $directories, string $outputFile)
    {
        $this->parser = (new ParserFactory())->createForNewestSupportedVersion();
        $this->directories = $directories;
        $this->outputFile = $outputFile;
    }

    public function extractRoutes()
    {
        $detected = strtolower(CMSDetector::detect($this->directories));
        $cmsType = match ($detected) {
            'wordpress' => 'WordPress',
            'drupal'    => 'Drupal',
            'joomla'    => 'Joomla',
            default     => 'unknown',
        };
        
        echo " Detected CMS type: $cmsType\n";


        $extractor = match ($cmsType) {
            'WordPress' => new WordPressExtractor($this->parser, $this->directories),
            'Drupal'    => new DrupalExtractor($this->parser, $this->directories),
            'Joomla'    => new JoomlaExtractor($this->parser, $this->directories),
            default     => null,
        };

        if (!$extractor) {
            echo " Unsupported or unknown CMS.\n";
            return;
        }

        $routes = $extractor->run();

        if (!is_dir(dirname($this->outputFile))) {
            mkdir(dirname($this->outputFile), 0777, true);
        }

        file_put_contents($this->outputFile, json_encode($routes, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
        echo " Extracted " . count($routes) . " routes to {$this->outputFile}\n";
    }
}

//  Usage example
$wpBase = '/var/www/html'; // adjust as needed

$extractor = new StaticRouteExtractor([
    "$wpBase/wp-content/plugins",
    "$wpBase/wp-content/themes",
    "$wpBase/wp-includes",
    "$wpBase/wp-admin",
], __DIR__ . '/output/static_routes_full.json');

$extractor->extractRoutes();

