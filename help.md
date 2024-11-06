# Welcome to SuShe! (SuperSheet)

SuShe! is a comprehensive tool designed to help you search for and manage albums using Spotify's vast music library. The end goal is to produce a proper Metal Awards list, suitable for submitting to the awards ceremony. This guide will help you get started and make the most out of the application's features.

---

## Getting Started

### Spotify API Credentials

- Before using SuShe!, ensure you have your Spotify API credentials set up. You need to obtain your own credentials from the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
- Go to the **Settings** tab and enter your **Client ID** and **Client Secret** obtained from the Spotify Developer Dashboard.
- Save your settings by clicking the **Save Spotify Settings** button.

### Preferred Music Player

- SuShe! allows you to choose your preferred music player between **Spotify** and **Tidal**.
- Go to the **Settings** tab and select your preferred music player from the **Preferred Music Player** dropdown.
- Save your settings by clicking the **Save Application Settings** button.
- This setting affects the links generated for albums in your list. When you click on an album title, it will open in your chosen music player.

### Telegram Submission Settings (Optional)

- If you wish to submit your album data via Telegram, enter your **Bot Token**, **Chat ID**, and **Message Thread ID** in the **Settings** tab.
- Save your settings by clicking the **Save Telegram Settings** button.
- **Note:** If you're participating in a group submission, these settings may be pre-configured for you.

---

## Using the Application

### Album List Tab

- **Viewing Your Album List:**
  - The **Album List** tab displays all the albums you've added.
  - **Album titles** in the list are clickable links that open in your preferred music player when clicked.
  - **Cover images** are displayed next to each album.
  - You can edit album details directly in the table, including country, genres, rating, and comments.

- **Adding Albums Manually:**
  - Go to **File > Add Album Manually** to open the manual entry dialog.
  - Fill in the album details, including artist, album name, release date, and optionally select a cover image.
  - Select the **country** and **genres** from predefined lists.
  - Enter a **rating** (0.00 to 5.00) and add any comments.
  - Click **Add Album** to include it in your list.

- **Adding Albums via Drag and Drop:**
  - **Drag and drop Spotify album or track links** directly into the application window.
  - For **album links**, the album will be added to your list.
  - For **track links**, the associated album will be added to your list.

- **Removing Albums:**
  - **Right-click** on an album in the list and select **Remove Album** to delete it.

- **Playing the Puzzle Game:**
  - Right-click on an album and select **Play Puzzle Game** to launch a fun puzzle featuring the album cover.

### Search Albums Tab

- **Searching for Artists:**
  - Enter an artist's name in the search box and press **Enter** or click **Search**.
  - A list of matching artists will appear.

- **Viewing Artist's Albums:**
  - **Double-click** on an artist to display their albums.
  - The albums will be listed with their release year.

- **Adding Albums from Search:**
  - **Double-click** on an album to fetch its details and add it to your album list.
  - A **notification** will appear when an album is added, displaying the album cover.

---

## File Operations

- **Saving Your Album Data:**
  - Go to **File > Save** to save your current album list.
  - Use **File > Save As...** to save the data to a new file.
  - Album data is saved in **JSON format**, including album details and cover images.
  - The application uses a **`points.json`** file to assign points to albums based on their rank when saving.

- **Opening Existing Data:**
  - Select **File > Open** to load a previously saved album list.
  - **Recent files** can be accessed from **File > Recent Files**.

- **Closing the Album Data:**
  - Choose **File > Close File** to clear the current album list.
  - You'll be prompted to save any unsaved changes.

- **Submitting via Telegram:**
  - If configured, use **File > Submit via Telegram** to send your album list to a Telegram chat.
  - Enter your name when prompted and confirm the submission.

- **Exiting the Application:**
  - Select **File > Quit** or press **Ctrl+Q** to exit the application.
  - Unsaved changes will prompt a save dialog.

---

## Additional Features

- **View Logs:**
  - Access the live log viewer via **File > View Logs** to see application logs in real-time.
  - Logs provide detailed information about application operations and any errors.

- **Help:**
  - Access this help dialog from **Help > Help**.

- **About SuShe:**
  - Learn more about SuShe! and find contact information via **About > About SuShe**.
  - The "About SuShe" dialog contains a clickable email address for support inquiries.

---

## Settings Tab

- **Spotify API Credentials:**
  - Manage your Spotify API credentials here.

- **Preferred Music Player:**
  - Choose your preferred music player (**Spotify** or **Tidal**).
  - This affects how album links are generated and opened.
  - When changing the preferred music player, **album links in your list are updated accordingly**.

- **Telegram Submission Settings:**
  - Configure your Telegram bot settings for submissions.

---

## Tips

- **Editing Album Details:**
  - Click on cells in the album table to edit details like **country**, **genres**, **rating**, and **comments**.

- **Selecting Genres and Countries:**
  - When adding or editing albums, select genres and countries from predefined lists for consistency.

- **Sorting Albums:**
  - Click on column headers in the album table to **sort your albums**.
  - By default, albums are sorted by the **Rating** column in descending order.

- **Unsaved Changes:**
  - An **asterisk (\*)** in the window title indicates unsaved changes.
  - The application will prompt you to save unsaved changes when closing or opening files.

- **Album Notifications:**
  - When you add an album, a **notification** appears displaying the album's cover image.

- **Cover Images:**
  - Cover images are displayed in your album list.
  - You can select a cover image when adding an album manually.

---

## Need Further Assistance?

If you encounter any issues or have questions, feel free to reach out to the support team!

- Contact us via email: [magnus+sushe@overli.dev](mailto:magnus+sushe@overli.dev)

Enjoy using SuShe!
