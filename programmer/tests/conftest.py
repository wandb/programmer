import warnings

# Disable the specific DeprecationWarning for distutils
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="The distutils package is deprecated and slated for removal",
)

# Disable SentryHubDeprecationWarning
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,  # or use SentryHubDeprecationWarning if it's a custom category
    message="`sentry_sdk.Hub` is deprecated and will be removed",
)
