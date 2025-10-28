# Dealing with Windows Defender

CrossPatch may be flagged by Windows Defender due to its functionality (file downloads, game file modifications, etc). This is common for mod management tools and doesn't indicate a real threat.

## For Users

1. Verify the Download:
   - Only download CrossPatch from the official GitHub releases page
   - Check that the download URL starts with `https://github.com/NickPlayzGITHUB/CrossPatch/releases/`
   - Compare the SHA-256 hash shown in the release notes with the downloaded file's hash

2. First-Run Instructions:
   When first running CrossPatch:
   - If Windows SmartScreen appears, click "More info"
   - Click "Run anyway" - this is normal for new applications
   - CrossPatch will ask for confirmation before performing sensitive operations

3. Optional: Add an Exclusion
   If you want to prevent future warnings:
   - Open Windows Security
   - Go to Virus & threat protection
   - Click "Manage settings" under "Virus & threat protection settings"
   - Scroll down to "Exclusions" and click "Add or remove exclusions"
   - Click "Add an exclusion" and select "Folder"
   - Browse to the CrossPatch installation folder

## Why Does Windows Defender Flag CrossPatch?

CrossPatch performs several legitimate operations that antivirus software may consider suspicious:
- Downloads mod files from GameBanana
- Modifies game files to install mods
- Extracts compressed files
- Checks for application updates

These are normal and necessary functions for a mod manager. CrossPatch:
- Only downloads from trusted sources (GameBanana, GitHub)
- Shows exactly what files it will modify
- Requires user confirmation for sensitive operations
- Uses secure HTTPS connections
- Verifies file integrity after downloads

## For Developers

1. Free Security Improvements:
   - Submit the application to Microsoft's [Windows Defender Security Intelligence portal](https://www.microsoft.com/wdsi/filesubmission)
   - Apply for free code signing through open source programs:
     - [SignPath Foundation](https://signpath.org/)
     - [DigiCert Open Source Project](https://www.digicert.com/open-source-software.htm)
   
2. Best Practices (Already Implemented):
   - File integrity verification
   - User confirmation dialogs
   - Secure download handling
   - Temporary file usage
   - Clear documentation of all operations

3. Helping Users:
   - Keep the release notes detailed
   - Include file hashes in releases
   - Document exactly what the app does
   - Provide clear security notices