# Design Document: Git Integration Rework for Programmer

## Overview
This document outlines the proposed changes to the Git integration feature of the `programmer` tool. The goal is to allow real-time edits in the user's working state while maintaining a separate commit history in a `programmer-<session>` branch, without affecting the user's visible working state.

## Objectives
- Allow users to see changes in real-time using tools like VSCode's Git view.
- Maintain a separate commit history in the background in a `programmer-<session>` branch.
- Avoid using stash or switching the HEAD, ensuring the user's working state remains unchanged.

## Proposed Solution
To achieve the above objectives, we propose the following solution:

### Session Branch Management
1. **Initialization**: At the start of a session, initialize a `programmer-<session>` branch based on the current state of the user's branch.

2. **Change Tracking**: Monitor file changes in the working directory to reflect them in the session branch, keeping the user's current branch and working directory unchanged.

3. **Commit History**: Maintain a separate commit history in the `programmer-<session>` branch to allow for session management and review without interfering with the user's workflow.

## Benefits
- Users can continue using their preferred development tools and see live changes.
- Maintains a clean separation of session history, enabling better session management and review.

## Challenges
- Requires careful handling of Git's internal mechanisms to ensure seamless integration.

## Conclusion
By leveraging a separate session branch, we can achieve seamless integration of the `programmer` tool with the user's workflow, providing real-time feedback and maintaining a comprehensive session history without disrupting the user's development environment.