# CrossPatch - A Crossworlds Mod Manager.

DISCLAIMER: AI was used in the assistance of making this program. 
While most of it is human there's also a lot of AI code, because this program needed to do some complicated stuff I can't wrap my head around


# What is CrossPatch?
CrossPatch is an easy to use mod manager for Sonic Racing: Crossworlds

## Features:
- Automatic Game Detection
- Automatic folder creation, no need to set up your ~mods folder in the game files
- Supports both Pak and UE4SS mods
- Support for custom mod display names, authors, version numbers, updating etc.
- Simple, Clean, and easy to use UI
- Ability to launch the game via CrossPatch
- Functions on both Windows and Linux

### Archive Support
CrossPatch supports extracting `.zip`, `.7z`, and `.rar` archives.

For `.7z` and `.rar` support, you may need to install additional tools:
- **.7z Support**: Provided by the `py7zr` Python package, which is installed automatically.
- **.rar Support**: CrossPatch can use a bundled `unrar` tool or a system-wide installation.
  - **Recommended (Bundled)**: Download the command-line tool from the official WinRAR website. Place `UnRAR.exe` (for Windows) or `unrar` (for Linux) inside the `assets` folder next to the CrossPatch executable.
  - **Alternative (System-wide)**: If the bundled tool is not found, CrossPatch will look for `unrar` in your system's PATH.
    - **Windows**: Install WinRAR and ensure its folder is in your PATH.
    - **Linux**: Install the `unrar` package via your distribution's package manager (e.g., `sudo apt install unrar` or `sudo dnf install unrar`).

## Misc Info

It is HIGHLY recommended that you run CrossPatch as an Admin or you are a Local Admin on your device. Not being an admin can inhibit CrossPatch from setting up your mods correctly and cause issues.

For setting up custom display names, authors and version to support CrossPatch, you just need to create a file named "info.json" in your mod folder

Below is a template you can use. The `mod_type` field is optional and defaults to `"pak"`. Use `"ue4ss-script"` for UE4SS script mods, or `"ue4ss-logic"` for UE4SS logic mods.

```json
{
  "name": "YOUR MOD NAME",
  "version": "1.0",
  "author": "Your Name",
  "mod_page": "https://gamebanana.com/mods/12345",
  "mod_type": "pak" 
}
```

## Privacy and Security

CrossPatch is designed to be safe and transparent.

### Privacy Policy

The application does not collect or transmit any personal user data. For more details, please see our [Privacy Policy](docs/PRIVACY.md).

### Code Signing Policy

To improve security and user trust, our official releases are signed.

*   Free code signing provided by [SignPath.io](https://signpath.io), certificate by SignPath Foundation.
*   **Committers and Reviewers**: [NockCS](https://github.com/NickPlayzGITHUB), [RED1](https://github.com/RED1-dev), [AntiApple4life](https://github.com/Anti-Apple4life), [Ben Thalmann](https://github.com/benthal)
*   **Approvers**: [NockCS](https://github.com/NickPlayzGITHUB)
```
