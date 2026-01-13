<?php

namespace src;

class CMSDetector
{
    public static function detect(array $directories): string
    {
        foreach ($directories as $dir) {
            // WordPress check: wp-settings.php or wp-includes/rest-api
            if (file_exists($dir . '/wp-settings.php') || strpos($dir, 'wp-content') !== false) {
                return 'wordpress';
            }

            // Drupal check: core/includes/bootstrap.inc or modules/
            if (file_exists($dir . '/core/includes/bootstrap.inc') || strpos($dir, 'modules') !== false) {
                return 'drupal';
            }

            // Joomla check: configuration.php or components/
            if (file_exists($dir . '/configuration.php') || strpos($dir, 'components') !== false) {
                return 'joomla';
            }
        }

        return 'unknown';
    }
}

