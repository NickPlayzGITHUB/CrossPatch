# CrossPatch - A Crossworlds Mod Manager.

DISCLAIMER: AI was used in the assistance of making this program. 
While most of it is human there's also a lot of AI code, because this program needed to do some complicated stuff I can't wrap my head around


# What is CrossPatch?
CrossPatch is an easy to use mod manager for Sonic Racing: Crossworlds

## Features:
- Automatic Game Detection (and custom directory support if it can't find the game)
- Automatic folder creation, no need to set up your ~mods folder in the game files
- Supports ALL Pak mods, even if they don't support CrossPatch
- For mods that do support Crosspatch, there's support for custom mod display names, authors, version numbers, etc.
- Simple, Clean, and easy to use UI
- Ability to launch the game via CrossPatch
- Functions on both Windows and Linux

## Misc Info

It is HIGHLY reccomended that you run CrossPatch as an Admin or you are a Local Admin on your device. Not being an admin can inhibit CrossPatch from setting up your mods correctly and cause issues.

For setting up custom display names, authors and version to support CrossPatch, you just need to create a file named "info.json" in your mod folder

Below is a template you can use. The `mod_type` field is optional and defaults to `"pak"`. Use `"ue4ss"` for UE4SS-based mods.

```json
{
  "name": "YOUR MOD NAME",
  "version": "1.0",
  "author": "Your Name",
  "mod_type": "pak" 
}
```
