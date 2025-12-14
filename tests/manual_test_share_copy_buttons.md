# Manual Test: Share and Copy Buttons Functionality

## Issue Description
The share and copy buttons on the web UI only work when an image has just been generated. They should also work when loading a history image.

## Test Steps

### Prerequisite
1. Start the Z-Image Studio server
2. Generate at least one image to have history

### Test Case 1: Share and Copy Buttons After New Generation
1. Fill in the prompt and generate a new image
2. Verify that the share and copy buttons are enabled (not disabled)
3. Click the share button - it should work (show share dialog or appropriate message)
4. Click the copy button - it should work (copy image to clipboard or show appropriate message)

### Test Case 2: Share and Copy Buttons After Loading History Image (Main Fix)
1. Click on the "History" button to open the history drawer
2. Click on any previously generated image from the history list
3. Verify that the image loads in the preview area
4. **CRITICAL TEST**: Verify that the share and copy buttons are now enabled (not disabled)
5. Click the share button - it should work with the loaded history image
6. Click the copy button - it should work with the loaded history image

### Test Case 3: Share and Copy Buttons Without Image
1. Clear the preview by refreshing the page or starting fresh
2. Verify that the share and copy buttons are disabled
3. Verify that clicking them shows appropriate error messages

## Expected Results
- After loading a history image, the share and copy buttons should be enabled
- The buttons should work with the loaded history image (same functionality as with newly generated images)
- Without an image, the buttons should be disabled

## Technical Details
The fix adds a call to `updateShareButtonState()` at the end of the `loadFromHistory()` function in `src/zimage/static/js/main.js`. This ensures that the share and copy buttons are properly enabled/disabled based on the availability of the loaded history image.

## Code Changes
```javascript
// In loadFromHistory() function, added at the end:
// Update share button state after loading history image
updateShareButtonState();
```

This ensures the button state is updated whenever a history image is loaded, making the share and copy functionality available for history images just like it is for newly generated images.