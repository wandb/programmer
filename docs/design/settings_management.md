# Settings Management Feature Design

Author: programmer

## Introduction

This document outlines the design for the settings management feature to be implemented in the 'programmer' project. The feature will allow users to manage settings related to weave logging and git tracking. These settings should persist across sessions and be stored in the user’s current directory.

## Feature Overview

The settings management feature will provide the following functionalities:

1. **Weave Logging Control**: Users can control the state of weave logging with three options:
   - Off
   - Local
   - Cloud

2. **Git Tracking Control**: Users can control the state of git tracking with two options:
   - Off
   - On

## Requirements

- The settings should persist across sessions.
- The settings should be stored in a file located in the user’s current directory.
- The feature should provide an easy interface for users to change settings.

## Design Details

### Settings Storage

- The settings will be stored in a directory named `.programmer` in the user's current directory.
- Within this directory, settings will be saved in a file named `settings`.
- The file will use a simple key-value format for storing settings:
  
  ```
  weave_logging=off
  git_tracking=on
  ```

### Interface

- A command-line interface will be provided to change settings. Users will be able to run commands such as:
  
  ```
  programmer settings set weave_logging local
  programmer settings get weave_logging
  ```

### Implementation Steps

1. **Create Settings Directory and File Structure**: Define the structure and location of the settings file within the `.programmer` directory.
2. **Implement CLI for Settings Management**: Develop commands to get and set the settings.
3. **Persist Settings Across Sessions**: Ensure that changes to settings are saved to the file and reloaded when the application starts.

## Conclusion

This design document provides a comprehensive overview of the settings management feature for the 'programmer' project. By following this design, we aim to implement a robust settings management system that allows users to control weave logging and git tracking effectively.