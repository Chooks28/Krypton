<?php

namespace src;

class Utils
{
    public static function normalizePath(string $path): string
    {
        return rtrim(str_replace('\\', '/', realpath($path)), '/');
    }
}

