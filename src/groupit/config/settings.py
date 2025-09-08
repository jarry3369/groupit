"""
Settings management with environment variables and configuration files.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from functools import lru_cache


@dataclass
class LLMSettings:
    """LLM provider settings"""
    provider: str = 'openai'
    api_key: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: Optional[int] = None
    timeout: int = 30
    retry_attempts: int = 3
    
    def __post_init__(self):
        """Load API key from environment if not provided"""
        if not self.api_key:
            env_key = f'{self.provider.upper()}_API_KEY'
            self.api_key = os.getenv(env_key)


@dataclass
class ClusteringSettings:
    """Clustering algorithm settings"""
    eps: float = 0.35
    min_samples: int = 2
    alpha: float = 0.4
    max_iterations: int = 2
    batch_size: int = 5


@dataclass
class PerformanceSettings:
    """Performance optimization settings"""
    enable_caching: bool = True
    cache_ttl: int = 3600  # seconds
    max_memory_mb: int = 1024
    enable_parallel_processing: bool = True
    max_workers: int = 4


@dataclass
class LoggingSettings:
    """Logging configuration settings"""
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = False


@dataclass
class Settings:
    """Main application settings"""
    
    # Core settings
    debug: bool = False
    verbose: bool = False
    
    # Component settings
    llm: LLMSettings = field(default_factory=LLMSettings)
    clustering: ClusteringSettings = field(default_factory=ClusteringSettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    
    # File paths
    config_file: Optional[Path] = None
    output_dir: Path = field(default_factory=lambda: Path.cwd())
    
    # Language support
    supported_languages: List[str] = field(default_factory=lambda: [
        'python', 'javascript', 'typescript', 'java', 'cpp', 'rust', 'go'
    ])
    
    @classmethod
    def from_env(cls) -> 'Settings':
        """Create settings from environment variables"""
        settings = cls()
        
        # Core settings
        settings.debug = os.getenv('GROUPIT_DEBUG', '').lower() in ('true', '1', 'yes')
        settings.verbose = os.getenv('GROUPIT_VERBOSE', '').lower() in ('true', '1', 'yes')
        
        # LLM settings
        settings.llm.provider = os.getenv('GROUPIT_LLM_PROVIDER', settings.llm.provider)
        settings.llm.temperature = float(os.getenv('GROUPIT_LLM_TEMPERATURE', settings.llm.temperature))
        settings.llm.timeout = int(os.getenv('GROUPIT_LLM_TIMEOUT', settings.llm.timeout))
        
        # Clustering settings
        settings.clustering.eps = float(os.getenv('GROUPIT_CLUSTERING_EPS', settings.clustering.eps))
        settings.clustering.min_samples = int(os.getenv('GROUPIT_CLUSTERING_MIN_SAMPLES', settings.clustering.min_samples))
        settings.clustering.batch_size = int(os.getenv('GROUPIT_CLUSTERING_BATCH_SIZE', settings.clustering.batch_size))
        
        # Performance settings
        settings.performance.enable_caching = os.getenv('GROUPIT_ENABLE_CACHING', '').lower() not in ('false', '0', 'no')
        settings.performance.max_memory_mb = int(os.getenv('GROUPIT_MAX_MEMORY_MB', settings.performance.max_memory_mb))
        settings.performance.max_workers = int(os.getenv('GROUPIT_MAX_WORKERS', settings.performance.max_workers))
        
        # Logging settings
        settings.logging.level = os.getenv('GROUPIT_LOG_LEVEL', settings.logging.level)
        settings.logging.file_path = os.getenv('GROUPIT_LOG_FILE')
        settings.logging.enable_file = bool(settings.logging.file_path)
        
        # Output directory
        output_dir = os.getenv('GROUPIT_OUTPUT_DIR')
        if output_dir:
            settings.output_dir = Path(output_dir)
            
        return settings
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'Settings':
        """Load settings from JSON configuration file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        settings = cls.from_env()  # Start with environment variables
        settings._update_from_dict(config_data)
        settings.config_file = config_path
        
        return settings
    
    def _update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update settings from dictionary data"""
        for key, value in data.items():
            if hasattr(self, key):
                if key == 'llm' and isinstance(value, dict):
                    self._update_llm_settings(value)
                elif key == 'clustering' and isinstance(value, dict):
                    self._update_clustering_settings(value)
                elif key == 'performance' and isinstance(value, dict):
                    self._update_performance_settings(value)
                elif key == 'logging' and isinstance(value, dict):
                    self._update_logging_settings(value)
                else:
                    setattr(self, key, value)
    
    def _update_llm_settings(self, data: Dict[str, Any]) -> None:
        """Update LLM settings from dictionary"""
        for key, value in data.items():
            if hasattr(self.llm, key):
                setattr(self.llm, key, value)
    
    def _update_clustering_settings(self, data: Dict[str, Any]) -> None:
        """Update clustering settings from dictionary"""
        for key, value in data.items():
            if hasattr(self.clustering, key):
                setattr(self.clustering, key, value)
    
    def _update_performance_settings(self, data: Dict[str, Any]) -> None:
        """Update performance settings from dictionary"""
        for key, value in data.items():
            if hasattr(self.performance, key):
                setattr(self.performance, key, value)
    
    def _update_logging_settings(self, data: Dict[str, Any]) -> None:
        """Update logging settings from dictionary"""
        for key, value in data.items():
            if hasattr(self.logging, key):
                setattr(self.logging, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return {
            'debug': self.debug,
            'verbose': self.verbose,
            'llm': {
                'provider': self.llm.provider,
                'temperature': self.llm.temperature,
                'timeout': self.llm.timeout,
                'retry_attempts': self.llm.retry_attempts
            },
            'clustering': {
                'eps': self.clustering.eps,
                'min_samples': self.clustering.min_samples,
                'alpha': self.clustering.alpha,
                'max_iterations': self.clustering.max_iterations,
                'batch_size': self.clustering.batch_size
            },
            'performance': {
                'enable_caching': self.performance.enable_caching,
                'cache_ttl': self.performance.cache_ttl,
                'max_memory_mb': self.performance.max_memory_mb,
                'enable_parallel_processing': self.performance.enable_parallel_processing,
                'max_workers': self.performance.max_workers
            },
            'logging': {
                'level': self.logging.level,
                'enable_console': self.logging.enable_console,
                'enable_file': self.logging.enable_file,
                'file_path': self.logging.file_path
            },
            'output_dir': str(self.output_dir),
            'supported_languages': self.supported_languages
        }
    
    def save_to_file(self, config_path: Path) -> None:
        """Save current settings to JSON file"""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def validate(self) -> List[str]:
        """Validate settings and return list of validation errors"""
        errors = []
        
        # Validate LLM settings
        from ..llm.providers.registry import provider_requires_api_key
        
        try:
            requires_key = provider_requires_api_key(self.llm.provider)
        except ValueError:
            # Provider not found, assume it requires API key for safety
            requires_key = True
        
        if not self.llm.api_key and requires_key:
            errors.append(f"API key required for {self.llm.provider} provider")
        
        if self.llm.temperature < 0 or self.llm.temperature > 2:
            errors.append("LLM temperature must be between 0 and 2")
        
        # Validate clustering settings
        if self.clustering.eps <= 0:
            errors.append("Clustering eps must be positive")
        
        if self.clustering.min_samples < 1:
            errors.append("Clustering min_samples must be at least 1")
        
        # Validate performance settings
        if self.performance.max_memory_mb < 64:
            errors.append("Maximum memory must be at least 64MB")
        
        if self.performance.max_workers < 1:
            errors.append("Maximum workers must be at least 1")
        
        return errors


# Global settings instance
_settings: Optional[Settings] = None


@lru_cache(maxsize=1)
def get_settings(config_file: Optional[Path] = None, force_reload: bool = False) -> Settings:
    """Get application settings (cached)"""
    global _settings
    
    if _settings is None or force_reload:
        if config_file and config_file.exists():
            _settings = Settings.from_file(config_file)
        else:
            _settings = Settings.from_env()
    
    return _settings


def update_settings(**kwargs) -> None:
    """Update global settings"""
    global _settings
    settings = get_settings()
    
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
    # Clear cache to force reload
    get_settings.cache_clear()
