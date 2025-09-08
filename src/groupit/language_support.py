#!/usr/bin/env python3
"""
Enhanced language support system with dynamic parser loading.
Supports a wide range of programming languages, build files, configuration files, and resource files.
"""

import re
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class FileCategory(Enum):
    """Categories of files for different handling strategies"""
    CODE = "code"                    # Programming languages
    CONFIG = "config"                # Configuration files
    BUILD = "build"                  # Build and dependency files
    RESOURCE = "resource"            # Images, fonts, assets
    DATA = "data"                    # Data files (JSON, XML, CSV, etc.)
    DOCUMENTATION = "documentation"   # Docs, README, etc.
    INFRASTRUCTURE = "infrastructure" # Docker, K8s, Terraform, etc.


@dataclass
class LanguageDefinition:
    """Definition of a language with its properties and parsers"""
    name: str
    category: FileCategory
    extensions: Set[str]
    import_pattern: Optional[re.Pattern] = None
    dependency_pattern: Optional[re.Pattern] = None
    comment_patterns: Dict[str, str] = field(default_factory=dict)  # single, multi
    block_delimiters: Dict[str, List[str]] = field(default_factory=dict)  # start, end
    tree_sitter_name: Optional[str] = None  # Tree-sitter grammar name
    metadata_extractors: List[Callable] = field(default_factory=list)
    
    def __post_init__(self):
        """Convert extension list to set if needed"""
        if isinstance(self.extensions, list):
            self.extensions = set(self.extensions)


class DynamicLanguageRegistry:
    """Registry for dynamically loading language definitions based on file extensions"""
    
    def __init__(self):
        self.languages: Dict[str, LanguageDefinition] = {}
        self.extension_map: Dict[str, str] = {}  # extension -> language_name
        self._initialize_builtin_languages()
    
    def _initialize_builtin_languages(self):
        """Initialize comprehensive language support"""
        
        # === PROGRAMMING LANGUAGES ===
        
        # JavaScript/TypeScript ecosystem
        self.register_language(LanguageDefinition(
            name="javascript",
            category=FileCategory.CODE,
            extensions={'.js', '.mjs', '.cjs'},
            import_pattern=re.compile(r"\b(?:import\s.+?from\s+|require\()\s*['\"]([@\w\-/\.]+)['\"]"),
            tree_sitter_name="javascript",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="typescript",
            category=FileCategory.CODE,
            extensions={'.ts', '.mts', '.cts'},
            import_pattern=re.compile(r"\b(?:import\s.+?from\s+|require\()\s*['\"]([@\w\-/\.]+)['\"]"),
            tree_sitter_name="typescript",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="tsx",
            category=FileCategory.CODE,
            extensions={'.tsx'},
            import_pattern=re.compile(r"\b(?:import\s.+?from\s+|require\()\s*['\"]([@\w\-/\.]+)['\"]"),
            tree_sitter_name="tsx",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="jsx",
            category=FileCategory.CODE,
            extensions={'.jsx'},
            import_pattern=re.compile(r"\b(?:import\s.+?from\s+|require\()\s*['\"]([@\w\-/\.]+)['\"]"),
            tree_sitter_name="javascript",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Python
        self.register_language(LanguageDefinition(
            name="python",
            category=FileCategory.CODE,
            extensions={'.py', '.pyi', '.pyx', '.pyw'},
            import_pattern=re.compile(r"\b(?:from\s+([\w\.]+)\s+import\s+|import\s+([\w\.]+))"),
            tree_sitter_name="python",
            comment_patterns={"single": "#", "multi": ['"""', '"""']}
        ))
        
        # Java ecosystem
        self.register_language(LanguageDefinition(
            name="java",
            category=FileCategory.CODE,
            extensions={'.java'},
            import_pattern=re.compile(r"\b(?:import\s+([\w\.]+);|package\s+([\w\.]+))"),
            tree_sitter_name="java",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="kotlin",
            category=FileCategory.CODE,
            extensions={'.kt', '.kts'},
            import_pattern=re.compile(r"\b(?:import\s+([\w\.]+)|package\s+([\w\.]+))"),
            tree_sitter_name="kotlin",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="scala",
            category=FileCategory.CODE,
            extensions={'.scala', '.sc'},
            import_pattern=re.compile(r"\b(?:import\s+([\w\.]+)|package\s+([\w\.]+))"),
            tree_sitter_name="scala",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="groovy",
            category=FileCategory.CODE,
            extensions={'.groovy', '.gvy', '.gy', '.gsh'},
            import_pattern=re.compile(r"\b(?:import\s+([\w\.]+)|package\s+([\w\.]+))"),
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # C/C++
        self.register_language(LanguageDefinition(
            name="c",
            category=FileCategory.CODE,
            extensions={'.c', '.h'},
            import_pattern=re.compile(r"\b(?:#include\s*[<\"]([\w\./]+)[>\"]|#import\s*[<\"]([\w\./]+)[>\"])"),
            tree_sitter_name="c",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="cpp",
            category=FileCategory.CODE,
            extensions={'.cpp', '.cc', '.cxx', '.c++', '.hpp', '.hh', '.hxx', '.h++'},
            import_pattern=re.compile(r"\b(?:#include\s*[<\"]([\w\./]+)[>\"]|#import\s*[<\"]([\w\./]+)[>\"])"),
            tree_sitter_name="cpp",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # C#
        self.register_language(LanguageDefinition(
            name="csharp",
            category=FileCategory.CODE,
            extensions={'.cs'},
            import_pattern=re.compile(r"\b(?:using\s+([\w\.]+);|namespace\s+([\w\.]+))"),
            tree_sitter_name="c_sharp",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Go
        self.register_language(LanguageDefinition(
            name="go",
            category=FileCategory.CODE,
            extensions={'.go'},
            import_pattern=re.compile(r"\b(?:import\s+[\"']([\w\./]+)[\"']|package\s+(\w+))"),
            tree_sitter_name="go",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Rust
        self.register_language(LanguageDefinition(
            name="rust",
            category=FileCategory.CODE,
            extensions={'.rs'},
            import_pattern=re.compile(r"\b(?:use\s+([\w:]+);|mod\s+(\w+);|extern\s+crate\s+(\w+))"),
            tree_sitter_name="rust",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # PHP
        self.register_language(LanguageDefinition(
            name="php",
            category=FileCategory.CODE,
            extensions={'.php', '.phtml', '.php3', '.php4', '.php5', '.php7', '.phps'},
            import_pattern=re.compile(r"\b(?:use\s+([\w\\]+);|require\s+[\"']([\w\./]+)[\"']|include\s+[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="php",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Ruby
        self.register_language(LanguageDefinition(
            name="ruby",
            category=FileCategory.CODE,
            extensions={'.rb', '.rbw', '.rake', '.gemspec'},
            import_pattern=re.compile(r"\b(?:require\s+[\"']([\w\./]+)[\"']|require_relative\s+[\"']([\w\./]+)[\"']|load\s+[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="ruby",
            comment_patterns={"single": "#"}
        ))
        
        # Swift
        self.register_language(LanguageDefinition(
            name="swift",
            category=FileCategory.CODE,
            extensions={'.swift'},
            import_pattern=re.compile(r"\b(?:import\s+([\w]+)|@testable\s+import\s+([\w]+))"),
            tree_sitter_name="swift",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Objective-C
        self.register_language(LanguageDefinition(
            name="objc",
            category=FileCategory.CODE,
            extensions={'.m', '.mm'},
            import_pattern=re.compile(r"\b(?:#import\s*[<\"]([\w\./]+)[>\"]|#include\s*[<\"]([\w\./]+)[>\"])"),
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Other modern languages
        self.register_language(LanguageDefinition(
            name="dart",
            category=FileCategory.CODE,
            extensions={'.dart'},
            import_pattern=re.compile(r"\b(?:import\s+[\"']([\w\./]+)[\"']|library\s+([\w\.]+))"),
            tree_sitter_name="dart",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # === MOBILE & NATIVE DEVELOPMENT ===
        
        # iOS/macOS Development
        self.register_language(LanguageDefinition(
            name="xcode_project",
            category=FileCategory.BUILD,
            extensions={'.pbxproj'},
            dependency_pattern=re.compile(r'(?:buildSettings|PRODUCT_BUNDLE_IDENTIFIER|FRAMEWORK_SEARCH_PATHS)'),
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="xcode_workspace",
            category=FileCategory.BUILD,
            extensions={'.xcworkspace'},
        ))
        
        self.register_language(LanguageDefinition(
            name="xcode_scheme",
            category=FileCategory.BUILD,
            extensions={'.xcscheme'},
        ))
        
        self.register_language(LanguageDefinition(
            name="ios_entitlements",
            category=FileCategory.CONFIG,
            extensions={'.entitlements'},
        ))
        
        self.register_language(LanguageDefinition(
            name="ios_provisioning",
            category=FileCategory.CONFIG,
            extensions={'.mobileprovision', '.provisionprofile'},
        ))
        
        self.register_language(LanguageDefinition(
            name="plist",
            category=FileCategory.CONFIG,
            extensions={'.plist'},
        ))
        
        self.register_language(LanguageDefinition(
            name="storyboard",
            category=FileCategory.RESOURCE,
            extensions={'.storyboard'},
        ))
        
        self.register_language(LanguageDefinition(
            name="xib",
            category=FileCategory.RESOURCE,
            extensions={'.xib'},
        ))
        
        # Android Development
        self.register_language(LanguageDefinition(
            name="android_manifest",
            category=FileCategory.CONFIG,
            extensions={'.xml'},
            dependency_pattern=re.compile(r'<uses-permission\s+android:name="([^"]+)"'),
        ))
        
        self.register_language(LanguageDefinition(
            name="android_resource",
            category=FileCategory.RESOURCE,
            extensions={'.xml'},  # Will be handled by special logic
        ))
        
        self.register_language(LanguageDefinition(
            name="android_binary",
            category=FileCategory.RESOURCE,
            extensions={'.apk', '.aar', '.dex'},
        ))
        
        # React Native
        self.register_language(LanguageDefinition(
            name="react_native_config",
            category=FileCategory.CONFIG,
            extensions={'.js', '.ts'},  # Will be handled by special logic for metro.config.js etc
        ))
        
        # Flutter
        self.register_language(LanguageDefinition(
            name="flutter_pubspec",
            category=FileCategory.BUILD,
            extensions={'.yaml', '.lock'},  # Will be handled by special filename logic
            dependency_pattern=re.compile(r'^\s*([a-zA-Z0-9_]+):\s*(.+)$', re.MULTILINE),
            comment_patterns={"single": "#"}
        ))
        
        # Unity
        self.register_language(LanguageDefinition(
            name="unity_scene",
            category=FileCategory.RESOURCE,
            extensions={'.unity'},
        ))
        
        self.register_language(LanguageDefinition(
            name="unity_asset",
            category=FileCategory.RESOURCE,
            extensions={'.asset', '.prefab', '.mat', '.physicMaterial'},
        ))
        
        self.register_language(LanguageDefinition(
            name="unity_meta",
            category=FileCategory.CONFIG,
            extensions={'.meta'},
        ))
        
        # === WEB DEVELOPMENT ===
        
        self.register_language(LanguageDefinition(
            name="html",
            category=FileCategory.CODE,
            extensions={'.html', '.htm', '.xhtml'},
            import_pattern=re.compile(r"\b(?:<link[^>]*href=[\"']([\w\./]+)[\"']|<script[^>]*src=[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="html",
            comment_patterns={"multi": ["<!--", "-->"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="css",
            category=FileCategory.CODE,
            extensions={'.css'},
            import_pattern=re.compile(r"\b(?:@import\s+[\"']([\w\./]+)[\"']|url\s*\(\s*[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="css",
            comment_patterns={"multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="scss",
            category=FileCategory.CODE,
            extensions={'.scss'},
            import_pattern=re.compile(r"\b(?:@import\s+[\"']([\w\./]+)[\"']|@use\s+[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="scss",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="sass",
            category=FileCategory.CODE,
            extensions={'.sass'},
            import_pattern=re.compile(r"\b(?:@import\s+[\"']([\w\./]+)[\"']|@use\s+[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="scss",
            comment_patterns={"single": "//"}
        ))
        
        self.register_language(LanguageDefinition(
            name="less",
            category=FileCategory.CODE,
            extensions={'.less'},
            import_pattern=re.compile(r"\b(?:@import\s+[\"']([\w\./]+)[\"'])"),
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Frontend frameworks
        self.register_language(LanguageDefinition(
            name="vue",
            category=FileCategory.CODE,
            extensions={'.vue'},
            import_pattern=re.compile(r"\b(?:import\s+[\"']([\w\./]+)[\"']|require\s+[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="vue",
            comment_patterns={"multi": ["<!--", "-->"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="svelte",
            category=FileCategory.CODE,
            extensions={'.svelte'},
            import_pattern=re.compile(r"\b(?:import\s+[\"']([\w\./]+)[\"']|from\s+[\"']([\w\./]+)[\"'])"),
            tree_sitter_name="svelte",
            comment_patterns={"multi": ["<!--", "-->"]}
        ))
        
        # === BUILD & DEPENDENCY FILES ===
        
        # Node.js ecosystem
        self.register_language(LanguageDefinition(
            name="package_json",
            category=FileCategory.BUILD,
            extensions={'.json'},
            dependency_pattern=re.compile(r'"([^"]+)"\s*:\s*"[^"]*"')
        ))
        
        # Python ecosystem
        self.register_language(LanguageDefinition(
            name="requirements",
            category=FileCategory.BUILD,
            extensions={'.txt'},
            dependency_pattern=re.compile(r'^([a-zA-Z0-9\-_]+)(?:[=<>!]+.*)?$', re.MULTILINE)
        ))
        
        self.register_language(LanguageDefinition(
            name="pipfile",
            category=FileCategory.BUILD,
            extensions={'.lock', '.toml'},
            dependency_pattern=re.compile(r'([a-zA-Z0-9\-_]+)\s*=')
        ))
        
        # Ruby ecosystem
        self.register_language(LanguageDefinition(
            name="gemfile",
            category=FileCategory.BUILD,
            extensions=set(),  # Special handling for Gemfile
            dependency_pattern=re.compile(r'gem\s+[\'"]([^\'"]+)[\'"]')
        ))
        
        # PHP ecosystem
        self.register_language(LanguageDefinition(
            name="composer",
            category=FileCategory.BUILD,
            extensions={'.json', '.lock'},
            dependency_pattern=re.compile(r'"([^"]+)"\s*:\s*"[^"]*"')
        ))
        
        # iOS/macOS
        self.register_language(LanguageDefinition(
            name="podfile",
            category=FileCategory.BUILD,
            extensions=set(),  # Special handling for Podfile
            dependency_pattern=re.compile(r"pod\s+['\"]([^'\"]+)['\"]")
        ))
        
        self.register_language(LanguageDefinition(
            name="cartfile",
            category=FileCategory.BUILD,
            extensions=set(),  # Special handling for Cartfile
            dependency_pattern=re.compile(r'(?:github|git|binary)\s+"([^"]+)"')
        ))
        
        # Java/Android ecosystem
        self.register_language(LanguageDefinition(
            name="gradle",
            category=FileCategory.BUILD,
            extensions={'.gradle', '.gradle.kts'},
            dependency_pattern=re.compile(r'(?:implementation|compile|api|testImplementation)\s+[\'"]([^\'"]+)[\'"]'),
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="maven",
            category=FileCategory.BUILD,
            extensions={'.xml'},
            dependency_pattern=re.compile(r'<artifactId>([^<]+)</artifactId>')
        ))
        
        # === CONFIGURATION FILES ===
        
        # Data formats
        self.register_language(LanguageDefinition(
            name="json",
            category=FileCategory.DATA,
            extensions={'.json', '.jsonc'},
            tree_sitter_name="json",
            comment_patterns={"single": "//"}  # JSONC support
        ))
        
        self.register_language(LanguageDefinition(
            name="yaml",
            category=FileCategory.DATA,
            extensions={'.yaml', '.yml'},
            import_pattern=re.compile(r"\b(?:imports?:|requires?:|depends?:)\s*([\w\./]+)"),
            tree_sitter_name="yaml",
            comment_patterns={"single": "#"}
        ))
        
        self.register_language(LanguageDefinition(
            name="toml",
            category=FileCategory.DATA,
            extensions={'.toml'},
            dependency_pattern=re.compile(r"\b(?:dependencies\s*=|dev-dependencies\s*=)"),
            tree_sitter_name="toml",
            comment_patterns={"single": "#"}
        ))
        
        self.register_language(LanguageDefinition(
            name="xml",
            category=FileCategory.DATA,
            extensions={'.xml', '.pom', '.xsd', '.wsdl'},
            tree_sitter_name="xml",
            comment_patterns={"multi": ["<!--", "-->"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="ini",
            category=FileCategory.CONFIG,
            extensions={'.ini', '.cfg', '.conf', '.config'},
            comment_patterns={"single": "#"}
        ))
        
        self.register_language(LanguageDefinition(
            name="env",
            category=FileCategory.CONFIG,
            extensions={'.env', '.env.local', '.env.development', '.env.production'},
            comment_patterns={"single": "#"}
        ))
        
        self.register_language(LanguageDefinition(
            name="properties",
            category=FileCategory.CONFIG,
            extensions={'.properties'},
            comment_patterns={"single": "#"}
        ))
        
        # === INFRASTRUCTURE & DEVOPS ===
        
        # Docker
        self.register_language(LanguageDefinition(
            name="dockerfile",
            category=FileCategory.INFRASTRUCTURE,
            extensions=set(),  # Special handling for Dockerfile
            import_pattern=re.compile(r"\b(?:FROM\s+([\w\./]+)|COPY\s+([\w\./]+)|ADD\s+([\w\./]+))"),
            comment_patterns={"single": "#"}
        ))
        
        self.register_language(LanguageDefinition(
            name="docker_compose",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # Kubernetes
        self.register_language(LanguageDefinition(
            name="kubernetes",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # Terraform
        self.register_language(LanguageDefinition(
            name="terraform",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.tf', '.tfvars'},
            import_pattern=re.compile(r"\b(?:module\s+\"([\w]+)\"|data\s+\"([\w]+)\")"),
            tree_sitter_name="hcl",
            comment_patterns={"single": "#", "multi": ["/*", "*/"]}
        ))
        
        # === RESOURCE FILES ===
        
        # Images
        self.register_language(LanguageDefinition(
            name="image_raster",
            category=FileCategory.RESOURCE,
            extensions={'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.avif', '.tiff', '.tif'}
        ))
        
        self.register_language(LanguageDefinition(
            name="image_vector",
            category=FileCategory.RESOURCE,
            extensions={'.svg', '.eps', '.ai', '.pdf'}
        ))
        
        # Fonts
        self.register_language(LanguageDefinition(
            name="font",
            category=FileCategory.RESOURCE,
            extensions={'.ttf', '.otf', '.woff', '.woff2', '.eot'}
        ))
        
        # Audio/Video
        self.register_language(LanguageDefinition(
            name="media",
            category=FileCategory.RESOURCE,
            extensions={'.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.avi', '.mov', '.webm', '.mkv'}
        ))
        
        # Archives
        self.register_language(LanguageDefinition(
            name="archive",
            category=FileCategory.RESOURCE,
            extensions={'.zip', '.tar', '.gz', '.bz2', '.7z', '.rar'}
        ))
        
        # === CI/CD & DEVOPS ===
        
        # GitHub Actions
        self.register_language(LanguageDefinition(
            name="github_actions",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # GitLab CI
        self.register_language(LanguageDefinition(
            name="gitlab_ci",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # Travis CI
        self.register_language(LanguageDefinition(
            name="travis_ci",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # CircleCI
        self.register_language(LanguageDefinition(
            name="circle_ci",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # Jenkins
        self.register_language(LanguageDefinition(
            name="jenkinsfile",
            category=FileCategory.INFRASTRUCTURE,
            extensions=set(),  # Special handling for Jenkinsfile
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        # Azure DevOps
        self.register_language(LanguageDefinition(
            name="azure_pipelines",
            category=FileCategory.INFRASTRUCTURE,
            extensions={'.yml', '.yaml'},
            comment_patterns={"single": "#"}
        ))
        
        # === VERSION CONTROL & GIT ===
        
        self.register_language(LanguageDefinition(
            name="gitignore",
            category=FileCategory.CONFIG,
            extensions=set(),  # Special handling for .gitignore
            comment_patterns={"single": "#"}
        ))
        
        self.register_language(LanguageDefinition(
            name="gitattributes",
            category=FileCategory.CONFIG,
            extensions=set(),  # Special handling for .gitattributes
            comment_patterns={"single": "#"}
        ))
        
        # === GAME DEVELOPMENT ===
        
        # Unreal Engine
        self.register_language(LanguageDefinition(
            name="unreal_project",
            category=FileCategory.BUILD,
            extensions={'.uproject', '.uplugin'},
        ))
        
        self.register_language(LanguageDefinition(
            name="unreal_asset",
            category=FileCategory.RESOURCE,
            extensions={'.uasset', '.umap'},
        ))
        
        # Godot
        self.register_language(LanguageDefinition(
            name="godot_project",
            category=FileCategory.BUILD,
            extensions={'.godot'},
        ))
        
        self.register_language(LanguageDefinition(
            name="godot_scene",
            category=FileCategory.RESOURCE,
            extensions={'.tscn', '.scn'},
        ))
        
        self.register_language(LanguageDefinition(
            name="godot_script",
            category=FileCategory.CODE,
            extensions={'.gd'},
            import_pattern=re.compile(r'\b(?:extends\s+(\w+)|preload\s*\(\s*["\']([^"\']+)["\']\s*\))'),
            tree_sitter_name="gdscript",
            comment_patterns={"single": "#"}
        ))
        
        # === EMBEDDED & IOT ===
        
        self.register_language(LanguageDefinition(
            name="arduino",
            category=FileCategory.CODE,
            extensions={'.ino', '.pde'},
            import_pattern=re.compile(r'#include\s*[<"]([^>"]+)[>"]'),
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="platformio",
            category=FileCategory.BUILD,
            extensions={'.ini'},  # platformio.ini
            comment_patterns={"single": "#", "single_alt": ";"}
        ))
        
        # === DATA SCIENCE & ML ===
        
        self.register_language(LanguageDefinition(
            name="jupyter_notebook",
            category=FileCategory.CODE,
            extensions={'.ipynb'},
            tree_sitter_name="json"
        ))
        
        self.register_language(LanguageDefinition(
            name="data_file",
            category=FileCategory.DATA,
            extensions={'.csv', '.tsv', '.json', '.parquet', '.h5', '.hdf5'},
        ))
        
        # === BLOCKCHAIN & WEB3 ===
        
        self.register_language(LanguageDefinition(
            name="solidity",
            category=FileCategory.CODE,
            extensions={'.sol'},
            import_pattern=re.compile(r'import\s+["\']([^"\']+)["\']'),
            tree_sitter_name="solidity",
            comment_patterns={"single": "//", "multi": ["/*", "*/"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="vyper",
            category=FileCategory.CODE,
            extensions={'.vy'},
            import_pattern=re.compile(r'from\s+([^\s]+)\s+import|import\s+([^\s]+)'),
            comment_patterns={"single": "#"}
        ))
        
        # === ADDITIONAL LANGUAGES ===
        
        # WebAssembly
        self.register_language(LanguageDefinition(
            name="webassembly",
            category=FileCategory.CODE,
            extensions={'.wasm', '.wat'},
            comment_patterns={"single": ";;"}
        ))
        
        # Shell scripts (more comprehensive)
        self.register_language(LanguageDefinition(
            name="shell",
            category=FileCategory.CODE,
            extensions={'.sh', '.bash', '.zsh', '.fish', '.csh', '.tcsh'},
            import_pattern=re.compile(r'(?:source|\.)\s+([^\s]+)'),
            tree_sitter_name="bash",
            comment_patterns={"single": "#"}
        ))
        
        # PowerShell
        self.register_language(LanguageDefinition(
            name="powershell",
            category=FileCategory.CODE,
            extensions={'.ps1', '.psm1', '.psd1'},
            import_pattern=re.compile(r'Import-Module\s+([^\s]+)'),
            comment_patterns={"single": "#", "multi": ["<#", "#>"]}
        ))
        
        # Batch files
        self.register_language(LanguageDefinition(
            name="batch",
            category=FileCategory.CODE,
            extensions={'.bat', '.cmd'},
            comment_patterns={"single": "REM", "single_alt": "::"}
        ))
        
        # === DOCUMENTATION ===
        
        self.register_language(LanguageDefinition(
            name="markdown",
            category=FileCategory.DOCUMENTATION,
            extensions={'.md', '.markdown', '.mdown', '.mkd'},
            import_pattern=re.compile(r"\b(?:!\[.*\]\(([\w\./]+)\)|\[.*\]\(([\w\./]+)\))"),
            tree_sitter_name="markdown",
            comment_patterns={"multi": ["<!--", "-->"]}
        ))
        
        self.register_language(LanguageDefinition(
            name="rst",
            category=FileCategory.DOCUMENTATION,
            extensions={'.rst', '.rest'},
            import_pattern=re.compile(r"\b(?:\.\.\s+include::\s+([\w\./]+)|\.\.\s+image::\s+([\w\./]+))")
        ))
        
        # === DATABASE ===
        
        self.register_language(LanguageDefinition(
            name="sql",
            category=FileCategory.CODE,
            extensions={'.sql', '.ddl', '.dml'},
            import_pattern=re.compile(r"\b(?:CREATE\s+DATABASE|USE\s+(\w+)|FROM\s+(\w+))"),
            tree_sitter_name="sql",
            comment_patterns={"single": "--", "multi": ["/*", "*/"]}
        ))
        
        # === SPECIAL FILE HANDLING ===
        
        # Add special filename handling for files without extensions
        self._add_special_files()
    
    def _add_special_files(self):
        """Add special filename patterns that don't follow extension rules"""
        special_files = {
            # === BUILD FILES ===
            'Gemfile': 'gemfile',
            'Gemfile.lock': 'gemfile',
            'Podfile': 'podfile',
            'Podfile.lock': 'podfile',
            'Cartfile': 'cartfile',
            'Cartfile.resolved': 'cartfile',
            'package.json': 'package_json',
            'package-lock.json': 'package_json',
            'yarn.lock': 'package_json',
            'pnpm-lock.yaml': 'package_json',
            'requirements.txt': 'requirements',
            'requirements-dev.txt': 'requirements',
            'Pipfile': 'pipfile',
            'Pipfile.lock': 'pipfile',
            'pyproject.toml': 'pipfile',
            'poetry.lock': 'pipfile',
            'composer.json': 'composer',
            'composer.lock': 'composer',
            'build.gradle': 'gradle',
            'settings.gradle': 'gradle',
            'pom.xml': 'maven',
            
            # === FLUTTER/DART ===
            'pubspec.yaml': 'flutter_pubspec',
            'pubspec.lock': 'flutter_pubspec',
            
            # === iOS/macOS BUILD FILES ===
            'project.pbxproj': 'xcode_project',
            'Podfile': 'podfile',
            'Podfile.lock': 'podfile',
            
            # === ANDROID BUILD FILES ===
            'AndroidManifest.xml': 'android_manifest',
            'build.gradle': 'gradle',
            'gradle.properties': 'properties',
            
            # === DOCKER ===
            'Dockerfile': 'dockerfile',
            'Dockerfile.dev': 'dockerfile',
            'Dockerfile.prod': 'dockerfile',
            'Dockerfile.test': 'dockerfile',
            'dockerfile': 'dockerfile',
            '.dockerignore': 'dockerfile',
            'docker-compose.yml': 'docker_compose',
            'docker-compose.yaml': 'docker_compose',
            'docker-compose.dev.yml': 'docker_compose',
            'docker-compose.prod.yml': 'docker_compose',
            'docker-compose.test.yml': 'docker_compose',
            'docker-compose.override.yml': 'docker_compose',
            
            # === CI/CD FILES ===
            # GitHub Actions
            '.github/workflows/ci.yml': 'github_actions',
            '.github/workflows/cd.yml': 'github_actions',
            '.github/workflows/build.yml': 'github_actions',
            '.github/workflows/test.yml': 'github_actions',
            '.github/workflows/deploy.yml': 'github_actions',
            # GitLab CI
            '.gitlab-ci.yml': 'gitlab_ci',
            # Travis CI
            '.travis.yml': 'travis_ci',
            # CircleCI
            'circle.yml': 'circle_ci',
            '.circleci/config.yml': 'circle_ci',
            # Azure DevOps
            'azure-pipelines.yml': 'azure_pipelines',
            # Jenkins
            'Jenkinsfile': 'jenkinsfile',
            # AppVeyor
            'appveyor.yml': 'travis_ci',
            
            # === CONFIGURATION FILES ===
            '.env': 'env',
            '.env.local': 'env',
            '.env.development': 'env',
            '.env.production': 'env',
            '.env.staging': 'env',
            '.env.test': 'env',
            '.env.example': 'env',
            '.envrc': 'env',
            
            # === BUILD TOOLS ===
            'Makefile': 'makefile',
            'makefile': 'makefile',
            'GNUmakefile': 'makefile',
            'CMakeLists.txt': 'cmake',
            'cmake': 'cmake',
            
            # === MOBILE DEVELOPMENT ===
            # React Native
            'metro.config.js': 'react_native_config',
            'react-native.config.js': 'react_native_config',
            'babel.config.js': 'react_native_config',
            # Expo
            'app.json': 'react_native_config',
            'expo.json': 'react_native_config',
            
            # === GAME DEVELOPMENT ===
            # Unity
            'ProjectSettings.asset': 'unity_asset',
            # Unreal
            'Default.uproject': 'unreal_project',
            # Godot
            'project.godot': 'godot_project',
            'export_presets.cfg': 'godot_project',
            
            # === VERSION CONTROL ===
            '.gitignore': 'gitignore',
            '.gitattributes': 'gitattributes',
            '.gitmodules': 'gitignore',
            '.gitkeep': 'gitignore',
            '.hgignore': 'gitignore',
            '.svnignore': 'gitignore',
            
            # === EMBEDDED & IOT ===
            'platformio.ini': 'platformio',
            'arduino.json': 'arduino',
            
            # === WEB DEVELOPMENT ===
            # Node.js configuration
            '.nvmrc': 'javascript',
            '.node-version': 'javascript',
            'tsconfig.json': 'typescript',
            'jsconfig.json': 'javascript',
            'webpack.config.js': 'javascript',
            'vite.config.js': 'javascript',
            'rollup.config.js': 'javascript',
            'nuxt.config.js': 'javascript',
            'next.config.js': 'javascript',
            # CSS preprocessors
            'tailwind.config.js': 'javascript',
            'postcss.config.js': 'javascript',
            # Linting and formatting
            '.eslintrc.js': 'javascript',
            '.eslintrc.json': 'json',
            '.prettierrc': 'json',
            '.stylelintrc': 'json',
            
            # === DOCUMENTATION ===
            'README': 'markdown',
            'README.md': 'markdown',
            'README.rst': 'rst',
            'CHANGELOG': 'markdown',
            'CHANGELOG.md': 'markdown',
            'HISTORY.md': 'markdown',
            'CONTRIBUTING': 'markdown',
            'CONTRIBUTING.md': 'markdown',
            'CODE_OF_CONDUCT.md': 'markdown',
            'SECURITY.md': 'markdown',
            'LICENSE': 'text',
            'LICENSE.txt': 'text',
            'LICENSE.md': 'markdown',
            'COPYING': 'text',
            'AUTHORS': 'text',
            'CONTRIBUTORS': 'text',
            'MAINTAINERS': 'text',
            'NOTICE': 'text',
            
            # === BLOCKCHAIN & WEB3 ===
            'truffle-config.js': 'javascript',
            'hardhat.config.js': 'javascript',
            'foundry.toml': 'toml',
            
            # === TERRAFORM ===
            'terraform.tfvars': 'terraform',
            'variables.tf': 'terraform',
            'outputs.tf': 'terraform',
            'main.tf': 'terraform',
            'providers.tf': 'terraform',
            
            # === KUBERNETES ===
            'deployment.yaml': 'kubernetes',
            'service.yaml': 'kubernetes',
            'configmap.yaml': 'kubernetes',
            'secret.yaml': 'kubernetes',
            'ingress.yaml': 'kubernetes',
            'pod.yaml': 'kubernetes',
            'namespace.yaml': 'kubernetes',
            'kustomization.yaml': 'kubernetes',
            
            # === MISC CONFIGS ===
            'supervisord.conf': 'ini',
            'nginx.conf': 'ini',
            'httpd.conf': 'ini',
            '.editorconfig': 'ini',
            'tox.ini': 'ini',
            'setup.cfg': 'ini',
            'pytest.ini': 'ini',
            'mypy.ini': 'ini',
            'bandit.yaml': 'yaml',
            '.pre-commit-config.yaml': 'yaml',
        }
        
        self.special_files = special_files
    
    def register_language(self, lang_def: LanguageDefinition):
        """Register a new language definition"""
        self.languages[lang_def.name] = lang_def
        
        # Update extension mapping
        for ext in lang_def.extensions:
            self.extension_map[ext.lower()] = lang_def.name
    
    def detect_language(self, file_path: str) -> Optional[str]:
        """Enhanced language detection from file path with comprehensive pattern matching"""
        path = Path(file_path)
        filename = path.name
        filename_lower = filename.lower()
        full_path_lower = str(path).lower()
        
        # === EXACT FILENAME MATCHING ===
        if hasattr(self, 'special_files'):
            # First try exact match (case-sensitive)
            if filename in self.special_files:
                return self.special_files[filename]
            # Then try lowercase match
            if filename_lower in self.special_files:
                return self.special_files[filename_lower]
        
        # === PATH PATTERN MATCHING ===
        
        # iOS/macOS Xcode Projects
        if 'project.pbxproj' in full_path_lower or filename_lower.endswith('.pbxproj'):
            return 'xcode_project'
        if (filename_lower.endswith('.xcworkspace') or '/xcworkspace/' in full_path_lower or
            'xcworkspacedata' in filename_lower):
            return 'xcode_workspace'
        if filename_lower.endswith('.xcscheme') or 'xcschemes' in full_path_lower:
            return 'xcode_scheme'
        
        # Android projects
        if 'androidmanifest.xml' in filename_lower:
            return 'android_manifest'
        if '/res/' in full_path_lower and filename_lower.endswith('.xml'):
            return 'android_resource'
        
        # CI/CD patterns
        if '.github/workflows/' in full_path_lower and filename_lower.endswith(('.yml', '.yaml')):
            return 'github_actions'
        if '.circleci/' in full_path_lower and filename_lower.endswith(('.yml', '.yaml')):
            return 'circle_ci'
        if '.gitlab-ci' in filename_lower:
            return 'gitlab_ci'
        if 'jenkinsfile' in filename_lower:
            return 'jenkinsfile'
        
        # Unity patterns
        if '/projectsettings/' in full_path_lower or 'projectsettings.asset' in filename_lower:
            return 'unity_asset'
        if filename_lower.endswith('.unity') or '/scenes/' in full_path_lower:
            return 'unity_scene'
        
        # === DOCKER PATTERNS ===
        dockerfile_patterns = [
            'dockerfile', 'dockerfile.', '.dockerfile',
            'docker-compose', 'dockercompose'
        ]
        for pattern in dockerfile_patterns:
            if pattern in filename_lower:
                if 'compose' in filename_lower:
                    return 'docker_compose'
                else:
                    return 'dockerfile'
        
        # === SPECIAL EXTENSION HANDLING ===
        extension = path.suffix.lower()
        if extension in self.extension_map:
            # YAML/YML files need special handling
            if extension in ['.yml', '.yaml']:
                return self._classify_yaml_file(filename_lower, full_path_lower)
            
            # JSON files need special handling
            elif extension == '.json':
                return self._classify_json_file(filename_lower, full_path_lower)
            
            # XML files need special handling  
            elif extension == '.xml':
                return self._classify_xml_file(filename_lower, full_path_lower)
            
            # JS/TS files need special handling
            elif extension in ['.js', '.ts']:
                return self._classify_js_ts_file(filename_lower, full_path_lower, extension)
            
            # INI files need special handling
            elif extension == '.ini':
                return self._classify_ini_file(filename_lower, full_path_lower)
            
            # Generic extension mapping
            return self.extension_map[extension]
        
        # === MULTI-EXTENSION HANDLING ===
        if len(path.suffixes) > 1:
            # Handle cases like .d.ts, .test.js, .config.js, etc.
            combined_ext = ''.join(path.suffixes[-2:]).lower()
            if combined_ext in self.extension_map:
                return self.extension_map[combined_ext]
            
            # Special multi-extension patterns
            if filename_lower.endswith('.d.ts'):
                return 'typescript'
            if any(pattern in filename_lower for pattern in ['.test.', '.spec.', '.e2e.']):
                if filename_lower.endswith('.js'):
                    return 'javascript'
                elif filename_lower.endswith('.ts'):
                    return 'typescript'
            if filename_lower.endswith('.config.js'):
                return 'javascript'
            if filename_lower.endswith('.config.ts'):
                return 'typescript'
        
        # === FILENAME PATTERN DETECTION ===
        
        # Configuration files without extensions
        config_patterns = {
            'dockerfile': 'dockerfile',
            'makefile': 'makefile',
            'gemfile': 'gemfile',
            'podfile': 'podfile',
            'cartfile': 'cartfile',
            'pipfile': 'pipfile',
            'procfile': 'procfile',
            'vagrantfile': 'ruby',
            'gulpfile': 'javascript',
            'gruntfile': 'javascript',
            'rakefile': 'ruby',
            'fastfile': 'ruby',
        }
        
        for pattern, lang in config_patterns.items():
            if filename_lower.startswith(pattern):
                return lang
        
        # === NO MATCH FOUND ===
        return None
    
    def _classify_yaml_file(self, filename_lower: str, full_path_lower: str) -> str:
        """Classify YAML files based on filename and path patterns"""
        # Docker Compose
        if 'docker-compose' in filename_lower or 'compose' in filename_lower:
            return 'docker_compose'
        
        # Kubernetes
        k8s_indicators = ['deployment', 'service', 'configmap', 'secret', 'pod', 
                          'namespace', 'ingress', 'daemonset', 'statefulset', 
                          'job', 'cronjob', 'persistentvolume']
        if any(indicator in filename_lower for indicator in k8s_indicators):
            return 'kubernetes'
        
        # CI/CD
        if any(ci_pattern in filename_lower for ci_pattern in 
               ['github', 'gitlab', 'travis', 'circle', 'azure', 'pipeline']):
            if 'github' in full_path_lower:
                return 'github_actions'
            elif 'gitlab' in filename_lower:
                return 'gitlab_ci'
            elif 'travis' in filename_lower:
                return 'travis_ci'
            elif 'circle' in filename_lower:
                return 'circle_ci'
            elif 'azure' in filename_lower:
                return 'azure_pipelines'
        
        # Flutter
        if 'pubspec' in filename_lower:
            return 'flutter_pubspec'
        
        # Generic YAML
        return 'yaml'
    
    def _classify_json_file(self, filename_lower: str, full_path_lower: str) -> str:
        """Classify JSON files based on filename patterns"""
        # Package managers
        if 'package' in filename_lower:
            return 'package_json'
        if 'composer' in filename_lower:
            return 'composer'
        
        # TypeScript/JavaScript configs
        if any(config in filename_lower for config in 
               ['tsconfig', 'jsconfig', 'babel', 'eslint', 'prettier']):
            return 'json'
        
        # Mobile development
        if any(mobile in filename_lower for mobile in ['app.json', 'expo']):
            return 'react_native_config'
        
        # Generic JSON
        return 'json'
    
    def _classify_xml_file(self, filename_lower: str, full_path_lower: str) -> str:
        """Classify XML files based on filename and path patterns"""
        # Android
        if 'androidmanifest' in filename_lower:
            return 'android_manifest'
        if '/res/' in full_path_lower or 'android' in full_path_lower:
            return 'android_resource'
        
        # Maven
        if 'pom.xml' in filename_lower:
            return 'maven'
        
        # iOS/macOS
        if filename_lower.endswith('.plist'):
            return 'plist'
        
        # Generic XML
        return 'xml'
    
    def _classify_js_ts_file(self, filename_lower: str, full_path_lower: str, extension: str) -> str:
        """Classify JavaScript/TypeScript files based on patterns"""
        # Configuration files
        config_patterns = ['config', 'webpack', 'rollup', 'vite', 'next', 
                          'nuxt', 'babel', 'jest', 'karma', 'protractor']
        if any(pattern in filename_lower for pattern in config_patterns):
            return 'javascript' if extension == '.js' else 'typescript'
        
        # React Native
        if any(rn_pattern in filename_lower for rn_pattern in 
               ['metro', 'react-native', 'rn-', 'expo']):
            return 'react_native_config'
        
        # Node.js files
        if filename_lower in ['server.js', 'app.js', 'index.js', 'main.js']:
            return 'javascript'
        
        # Default based on extension
        return 'javascript' if extension == '.js' else 'typescript'
    
    def _classify_ini_file(self, filename_lower: str, full_path_lower: str) -> str:
        """Classify INI files based on filename patterns"""
        # PlatformIO specific
        if 'platformio.ini' in filename_lower:
            return 'platformio'
        
        # Other specific INI files
        specific_inis = {
            'setup.cfg': 'ini',
            'tox.ini': 'ini',
            'pytest.ini': 'ini',
            'mypy.ini': 'ini',
            'supervisord.conf': 'ini',
            '.editorconfig': 'ini',
        }
        
        for specific_file, lang in specific_inis.items():
            if specific_file in filename_lower:
                return lang
        
        # Generic INI
        return 'ini'
    
    def get_language_def(self, lang_name: str) -> Optional[LanguageDefinition]:
        """Get language definition by name"""
        return self.languages.get(lang_name)
    
    def get_supported_extensions(self) -> Set[str]:
        """Get all supported file extensions"""
        extensions = set()
        for lang_def in self.languages.values():
            extensions.update(lang_def.extensions)
        return extensions
    
    def get_languages_by_category(self, category: FileCategory) -> List[LanguageDefinition]:
        """Get all languages in a specific category"""
        return [lang_def for lang_def in self.languages.values() 
                if lang_def.category == category]
    
    def analyze_staged_files(self, repo_root: Path, staged_files: List[str]) -> Dict[str, Any]:
        """Analyze staged files and determine required parsers"""
        analysis = {
            'languages_detected': set(),
            'categories': set(),
            'parsers_needed': set(),
            'file_types': {},
            'special_files': [],
            'unsupported_files': []
        }
        
        for file_path in staged_files:
            lang_name = self.detect_language(file_path)
            
            if lang_name:
                lang_def = self.get_language_def(lang_name)
                if lang_def:
                    analysis['languages_detected'].add(lang_name)
                    analysis['categories'].add(lang_def.category.value)
                    analysis['file_types'][file_path] = {
                        'language': lang_name,
                        'category': lang_def.category.value,
                        'has_tree_sitter': bool(lang_def.tree_sitter_name),
                        'has_import_pattern': bool(lang_def.import_pattern),
                        'has_dependency_pattern': bool(lang_def.dependency_pattern)
                    }
                    
                    # Determine needed parsers
                    if lang_def.tree_sitter_name:
                        analysis['parsers_needed'].add(f"tree_sitter_{lang_def.tree_sitter_name}")
                    if lang_def.category == FileCategory.RESOURCE:
                        analysis['parsers_needed'].add(f"resource_parser")
                    if lang_def.category == FileCategory.BUILD:
                        analysis['parsers_needed'].add(f"build_parser")
            else:
                analysis['unsupported_files'].append(file_path)
        
        # Convert sets to lists for JSON serialization
        analysis['languages_detected'] = list(analysis['languages_detected'])
        analysis['categories'] = list(analysis['categories'])
        analysis['parsers_needed'] = list(analysis['parsers_needed'])
        
        return analysis


# Global registry instance
language_registry = DynamicLanguageRegistry()


# === PARSER CLASSES ===

class BaseParser(ABC):
    """Base class for all file parsers"""
    
    @abstractmethod
    def can_parse(self, file_path: str, content: str) -> bool:
        """Check if this parser can handle the file"""
        pass
    
    @abstractmethod
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """Parse the file and return extracted information"""
        pass


class ResourceFileParser(BaseParser):
    """Parser for resource files (images, fonts, etc.)"""
    
    def can_parse(self, file_path: str, content: str) -> bool:
        lang_name = language_registry.detect_language(file_path)
        if lang_name:
            lang_def = language_registry.get_language_def(lang_name)
            return lang_def and lang_def.category == FileCategory.RESOURCE
        return False
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """Parse resource file (mainly metadata)"""
        path = Path(file_path)
        
        # Basic file information
        result = {
            'file_path': file_path,
            'file_size': len(content) if isinstance(content, str) else 0,
            'file_type': 'resource',
            'extension': path.suffix.lower(),
            'imports': [],
            'dependencies': [],
            'metadata': {}
        }
        
        # Try to detect file type specifics
        lang_name = language_registry.detect_language(file_path)
        if lang_name:
            result['language'] = lang_name
            result['metadata']['detected_type'] = lang_name
        
        # For text-based resources, try to extract some metadata
        if isinstance(content, str) and len(content) > 0:
            # Look for common patterns in resource files
            if path.suffix.lower() == '.svg':
                # SVG specific parsing
                import_matches = re.findall(r'href=[\'"]([^\'"]+)[\'"]', content)
                result['imports'] = list(set(import_matches))
                
                # Extract dimensions if present
                width_match = re.search(r'width=[\'"]([^\'"]+)[\'"]', content)
                height_match = re.search(r'height=[\'"]([^\'"]+)[\'"]', content)
                if width_match:
                    result['metadata']['width'] = width_match.group(1)
                if height_match:
                    result['metadata']['height'] = height_match.group(1)
        
        return result


class BuildFileParser(BaseParser):
    """Parser for build and dependency files"""
    
    def can_parse(self, file_path: str, content: str) -> bool:
        lang_name = language_registry.detect_language(file_path)
        if lang_name:
            lang_def = language_registry.get_language_def(lang_name)
            return lang_def and lang_def.category == FileCategory.BUILD
        return False
    
    def parse(self, file_path: str, content: str) -> Dict[str, Any]:
        """Parse build file and extract dependencies"""
        result = {
            'file_path': file_path,
            'file_type': 'build',
            'imports': [],
            'dependencies': [],
            'metadata': {}
        }
        
        lang_name = language_registry.detect_language(file_path)
        if not lang_name:
            return result
            
        lang_def = language_registry.get_language_def(lang_name)
        if not lang_def:
            return result
        
        result['language'] = lang_name
        
        # Extract dependencies using the language-specific pattern
        if lang_def.dependency_pattern and content:
            dependencies = []
            matches = lang_def.dependency_pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle multiple capture groups
                    dep = next((m for m in match if m), '')
                else:
                    dep = match
                if dep:
                    dependencies.append(dep)
            result['dependencies'] = list(set(dependencies))
        
        # Special handling for different build file types
        path = Path(file_path)
        filename = path.name.lower()
        
        if filename in ['package.json', 'composer.json']:
            self._parse_json_dependencies(content, result)
        elif filename.startswith('requirements') and filename.endswith('.txt'):
            self._parse_requirements_file(content, result)
        elif filename in ['gemfile', 'podfile'] or path.name in ['Gemfile', 'Podfile']:
            self._parse_ruby_style_dependencies(content, result)
        elif filename.endswith('.gradle') or filename in ['build.gradle', 'settings.gradle']:
            self._parse_gradle_dependencies(content, result)
        
        return result
    
    def _parse_json_dependencies(self, content: str, result: Dict[str, Any]):
        """Parse JSON-based dependency files"""
        try:
            data = json.loads(content)
            deps = []
            for key in ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']:
                if key in data:
                    deps.extend(data[key].keys())
            result['dependencies'] = deps
            
            # Extract metadata
            if 'name' in data:
                result['metadata']['package_name'] = data['name']
            if 'version' in data:
                result['metadata']['version'] = data['version']
                
        except json.JSONDecodeError:
            pass
    
    def _parse_requirements_file(self, content: str, result: Dict[str, Any]):
        """Parse Python requirements file"""
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract package name (before any version specifiers)
                match = re.match(r'^([a-zA-Z0-9\-_\.]+)', line)
                if match:
                    deps.append(match.group(1))
        result['dependencies'] = deps
    
    def _parse_ruby_style_dependencies(self, content: str, result: Dict[str, Any]):
        """Parse Ruby-style dependency files (Gemfile, Podfile)"""
        deps = []
        gem_pattern = re.compile(r'(?:gem|pod)\s+[\'"]([^\'"]+)[\'"]')
        matches = gem_pattern.findall(content)
        result['dependencies'] = list(set(matches))
    
    def _parse_gradle_dependencies(self, content: str, result: Dict[str, Any]):
        """Parse Gradle build file dependencies"""
        deps = []
        # Match various dependency declarations
        patterns = [
            r'(?:implementation|compile|api|testImplementation|androidTestImplementation)\s+[\'"]([^\'"]+)[\'"]',
            r'(?:implementation|compile|api|testImplementation|androidTestImplementation)\s+group:\s*[\'"]([^\'"]+)[\'"]'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            deps.extend(matches)
        
        result['dependencies'] = list(set(deps))


class DynamicParserLoader:
    """Dynamically loads and manages parsers based on detected file types"""
    
    def __init__(self):
        self.parsers: List[BaseParser] = []
        self.loaded_parsers: Set[str] = set()
        self._register_builtin_parsers()
    
    def _register_builtin_parsers(self):
        """Register built-in parsers"""
        self.parsers.extend([
            ResourceFileParser(),
            BuildFileParser(),
        ])
        self.loaded_parsers.update(['resource_parser', 'build_parser'])
    
    def load_parser_for_files(self, staged_files: List[str]) -> List[str]:
        """Load required parsers for the given files"""
        analysis = language_registry.analyze_staged_files(Path.cwd(), staged_files)
        
        loaded = []
        for parser_name in analysis['parsers_needed']:
            if parser_name not in self.loaded_parsers:
                success = self._load_parser(parser_name)
                if success:
                    loaded.append(parser_name)
                    self.loaded_parsers.add(parser_name)
        
        return loaded
    
    def _load_parser(self, parser_name: str) -> bool:
        """Load a specific parser"""
        # For tree-sitter parsers, we would dynamically import them
        if parser_name.startswith('tree_sitter_'):
            lang = parser_name.replace('tree_sitter_', '')
            try:
                # This would be where we dynamically import tree-sitter grammars
                # For now, we'll just mark it as loaded
                return True
            except ImportError:
                return False
        
        return True
    
    def parse_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Parse a file using the appropriate parser"""
        for parser in self.parsers:
            if parser.can_parse(file_path, content):
                return parser.parse(file_path, content)
        
        # Fallback: basic file information
        return {
            'file_path': file_path,
            'file_type': 'unknown',
            'imports': [],
            'dependencies': [],
            'metadata': {}
        }


# Global parser loader instance
parser_loader = DynamicParserLoader()


# === UTILITY FUNCTIONS ===

def get_supported_extensions() -> Set[str]:
    """Get all supported file extensions"""
    return language_registry.get_supported_extensions()


def detect_language_from_path(file_path: str) -> Optional[str]:
    """Detect language from file path"""
    return language_registry.detect_language(file_path)


def analyze_staged_files_for_parsers(staged_files: List[str]) -> Dict[str, Any]:
    """Analyze staged files and determine what parsers are needed"""
    return language_registry.analyze_staged_files(Path.cwd(), staged_files)


def load_parsers_for_files(staged_files: List[str]) -> List[str]:
    """Load required parsers for staged files"""
    return parser_loader.load_parser_for_files(staged_files)


def parse_file_with_dynamic_parser(file_path: str, content: str) -> Dict[str, Any]:
    """Parse file using dynamically loaded parser"""
    return parser_loader.parse_file(file_path, content)


def get_extensions_by_category(category: FileCategory) -> Set[str]:
    """Get all file extensions for a specific category"""
    extensions = set()
    for lang_def in language_registry.languages.values():
        if lang_def.category == category:
            extensions.update(lang_def.extensions)
    return extensions


def get_image_extensions() -> Set[str]:
    """Get all image file extensions (both raster and vector)"""
    return get_raster_image_extensions() | get_vector_image_extensions()


def get_raster_image_extensions() -> Set[str]:
    """Get raster image file extensions"""
    raster_lang = language_registry.get_language_def('image_raster')
    return raster_lang.extensions if raster_lang else set()


def get_vector_image_extensions() -> Set[str]:
    """Get vector image file extensions"""  
    vector_lang = language_registry.get_language_def('image_vector')
    return vector_lang.extensions if vector_lang else set()


def get_config_extensions() -> Set[str]:
    """Get configuration file extensions"""
    return get_extensions_by_category(FileCategory.CONFIG) | get_extensions_by_category(FileCategory.DATA)


def get_documentation_extensions() -> Set[str]:
    """Get documentation file extensions"""
    return get_extensions_by_category(FileCategory.DOCUMENTATION)


def get_build_extensions() -> Set[str]:
    """Get build and dependency file extensions"""
    return get_extensions_by_category(FileCategory.BUILD)


def categorize_file_by_extension(file_path: str) -> Optional[str]:
    """Categorize a file based on its extension using the language registry"""
    lang_name = detect_language_from_path(file_path)
    if lang_name:
        lang_def = language_registry.get_language_def(lang_name)
        if lang_def:
            return lang_def.category.value
    
    # Special handling for test files
    file_path_lower = file_path.lower()
    if 'test' in file_path_lower or 'spec' in file_path_lower:
        return 'test'
    
    return None
