<?php

/*
    Silo -- a simple, general purpose file system for LSL via HTTP
        version 2006-07-09-beta
        by Zero Linden
    
        Copyright (c) 2006 Linden Lab
        Licensed under the "MIT" open source license.
    
    This file is only part of the whole distribution.
        silo.php -- the main impelmentation
*/

header('Content-Type: text/plain;charset=utf-8');

$hexPat = "[0-9a-f]";
$keyPat = "$hexPat{8}-$hexPat{4}-$hexPat{4}-$hexPat{4}-$hexPat{12}";
$partPat = "[-+_0-9a-z%]+";
$firstPat = $partPat;
//$firstPat = $keyPat;
    // set to $keyPat to allow only paths starting with keys
$pathPattern = <<<END
	{^
        /
            ($firstPat)
            ((?:
                /
                $partPat
            ){0,10})
		(/?)
	$}ix
END;

$filePattern = "{^($partPat)(\\.data|\\.meta)?$}i";


function parsePath($path)
{
    global $pathPattern, $hexPat;
    
    if (!preg_match($pathPattern, $path, $parts)) {
    	httpError(400, "Bad Request", "pattern failure in: $path");
    }
    
    $first = strtolower($parts[1]);
    $middle = strtolower($parts[2]);
    $isDir = $parts[3] == "/";

    $first = preg_replace('/(..)(?=.)/', '$1/', $first, 2);
        // spread the first path part across two directory levels
        
    return array(
        'isDir' => $isDir,
        'translatedPath' => "data/$first$middle"
        );
}

function httpError($status, $message, $detail = "while processing")
{
    global $pathInfo;
    
	header("HTTP/1.0 $status $message");
    echo $detail, ": ", $pathInfo, "\n";
    exit;
}

function mkdirAsNeeded($path, $mode = 0777)
{
    $oldMask = umask(0);
    $pathSoFar = '';
    foreach (explode('/', $path) as $part) {
        if (!$part) continue;
        $pathSoFar .= $part;
        @mkdir($pathSoFar, $mode);
        $pathSoFar .= '/';
    }
    umask($oldMask);
}

function rmdirAndContents($dir)
{
    global $filePattern;
    
    $h = @opendir($dir);
    if (!$h) { return; }
    while (($name = readdir($h)) !== false) {
        if (preg_match($filePattern, $name)) {
            $item = $dir . "/" . $name;
            if (is_dir($item))  rmdirAndContents($item);
            else                @unlink($item);
        }
    }
    closedir($h);
    @rmdir($dir);
}


function getFile($dataFile, $metaFile)
{    
	if (!is_readable($dataFile)) {
	   httpError(404, "Not Found", "no data for");
    }
    
    $replayedHeaderLines = "{^(Content-Type)\\s*:}i";
    foreach (file($metaFile) as $line) {
        if (preg_match($replayedHeaderLines, $line)) {
            header($line);
        }
    }
    
    copy($dataFile, "php://output");
}

function putFile($dataFile, $metaFile)
{
    mkdirAsNeeded(dirname($dataFile));
    
    $preexists = file_exists($dataFile);
    copy("php://input", $dataFile);
	if (!is_writable($dataFile)) {
	   httpError(403, "Forbidden", "can't modify");
    }
    
    $storedHeaders = "{^(Content-Type|X-SecondLife-\\S*)\\s*$}i";
    $h = fopen($metaFile, "w");
    foreach (apache_request_headers() as $header => $value) {
        if (preg_match($storedHeaders, $header, $matches)) {
            fwrite($h, strtolower($matches[1]) . ": $value\n");
        }
    }
    fclose($h);
    
    if (!$preexists) {
      	header("HTTP/1.0 201 Created");
    }
}

function delFile($dataFile, $metaFile)
{
	if (!unlink($dataFile)  ||  !unlink($metaFile)) {
	   if (is_file($dataFile)  ||  is_file($metaFile)) {
           httpError(403, "Forbidden", "can't modify");
       }
    }
}

function getDir($dirPath)
{
    global $filePattern;
    
    if (!is_dir($dirPath)) {
        httpError(404, "Not Found", "no data at");
    }
    
    $h = opendir($dirPath);
    if (!$h) {
       httpError(403, "Forbidden", "can't read");
    }
    $files = array();
    while (($f = readdir($h)) !== false) {
        if (preg_match($filePattern, $f, $m)) {
            $files[] = $m[1];
        }
    }
    $files = array_unique($files);
    sort($files);    // some versions of PHP's array_unique don't always sort!
    foreach ($files as $f) {
        echo $f, "\n";
    }
}

function delDir($dirPath)
{
    rmdirAndContents($dirPath);
	if (is_dir($dirPath)) {
	   httpError(403, "Forbidden", "can't modify");
    }
}


$requestURI = $_SERVER['REQUEST_URI'];
$scriptName = $_SERVER['SCRIPT_NAME'];
$pathInfo = strtolower(substr($requestURI, strlen($scriptName)));
    // Note: not using $_SERVER['PATH_INFO'] as it is URL decoded

$method = $_SERVER['REQUEST_METHOD'];

if (version_compare(PHP_VERSION, "4.3.0", "<")) {
	header("HTTP/1.0 500 Internal Server Error");
    echo "PHP version incompatible: ", PHP_VERSION, "\n";
    exit;
}

$parse = parsePath($pathInfo);

if (! $parse['isDir']) {
    $dataFile = $parse['translatedPath'] . ".data";
    $metaFile = $parse['translatedPath'] . ".meta";

    if     ($method == 'GET')       getFile($dataFile, $metaFile);
    elseif ($method == 'PUT')       putFile($dataFile, $metaFile);
    elseif ($method == 'DELETE')    delFile($dataFile, $metaFile);
    else                            httpError(405, "Method Not Allowed");
}
else {
    $dirPath = $parse['translatedPath'];

    if     ($method == 'GET')       getDir($dirPath);
    elseif ($method == 'DELETE')    delDir($dirPath);
    else                            httpError(405, "Method Not Allowed");
}


?>
