# YouTube Music AI Playlist Curator 🎵

An intelligent tool that helps you create curated sub-playlists from your existing YouTube Music playlists using AI. This tool analyzes your music library and creates new playlists based on specific genres, moods, artists, or other criteria you define.

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![YTMusicAPI](https://img.shields.io/badge/YTMusicAPI-Support-red.svg)](https://ytmusicapi.readthedocs.io/)
[![Gemini AI](https://img.shields.io/badge/Gemini%20AI-Powered-blueviolet.svg)](https://ai.google.dev/)

## ✨ Features

- **AI-Powered Curation:** Uses Google's Gemini AI to intelligently select songs matching your criteria
- **Detail-Oriented:** Creates playlists based on genres, moods, artists, and other specific parameters
- **User-Friendly:** Simple command-line interface with clear prompts
- **Smart Matching:** Uses fuzzy matching to ensure accurate song identification
- **Human-Like Behavior:** Mimics natural user behavior to avoid API limitations
- **Batch Processing:** Efficiently handles large playlists by processing songs in batches

## ⚠️ DISCLAIMER

Avoid excessive use with large playlists in a single day, as it may trigger YouTube's restrictions, potentially preventing you from watching videos or listening to music temporarily. In testing, using it approximately 5–6 times in a day did not cause any issues.

## 📋 Prerequisites

- Python 3.9 or higher
- A Google account with YouTube Music
- Google Gemini API key (easily obtained through Google AI Studio)

## 🔧 Installation

1. **Clone the repository:**
```bash
git clone https://github.com/AbhishekBarali/AI_Playlist_Curator.git
cd AI_Playlist_Curator
```

Don't have Git? No worries! Just click the green "Code" button at the top of this page and select "Download ZIP", then extract it to a folder on your computer.

2. **Create a virtual environment (Optional but recommended):**
```bash
# Create virtual environment
python -m venv ytmusicp

# On Windows
ytmusicp\Scripts\activate

# On macOS/Linux
source ytmusicp/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Set up your API keys:**
   - Inside the `.env` file in the project root directory
   - Add your Google Gemini API key:
   ```
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

   - If you don't know how to get it:
     1. Go to Google AI Studio (simply login using your Google ID)
     2. Click on "Get API Key" on the top right
     3. Click on "Create API key"
     4. Copy the key

5. **Set up YouTube Music authentication:**
   - Run the following command:
   ```bash
   ytmusicapi oauth
   ```
   - Follow the on-screen instructions to complete the authentication process

   **Detailed Authentication Instructions:**
   1. Press Ctrl-Shift-I to open the Network Tab in your browser
   2. Click on the Library on the left side to load POST requests in your Network Tab
   3. Find and click on a request that looks like YouTube Music API
   4. Click on the "Raw" button and select all the text
   5. Paste the raw text when prompted by the script
   6. The script will generate a code to paste inside "headers_auth.json"

## 🚀 Usage

1. **Run the script:**
```bash
python main.py
```

2. **Follow the interactive prompts:**
   - Select a source playlist from your YouTube Music library
   - Enter criteria for your new playlist:
     - Title (required)
     - Description (optional)
     - Genres (optional)
     - Artists (optional)
     - Moods/vibes (optional)
     - Keywords (optional)

3. **Review and confirm:**
   - The AI will analyze your songs and suggest matches based on your criteria
   - You'll see which songs were matched and have the option to proceed
   - The script will create the new playlist and add the selected songs

4. **Access your new playlist:**
   - Once completed, you'll receive a direct link to your new playlist
   - You can also find it in your YouTube Music library

## 📝 Example

Here's an example of creating a workout playlist:

```
Starting AI Playlist Curator...
Initializing YouTube Music client...
YouTube Music client initialized successfully.
Initializing Gemini AI model ('gemini-2.0-flash')...
Gemini AI model initialized successfully.

Fetching your YouTube Music playlists...

Your Playlists:
1. Liked Music
2. All Songs
3. Discover Mix
4. My Mix

Enter the number of the playlist to organize: 2

You selected playlist: 'All Songs'

Fetching songs from playlist 'All Songs'...
Note: Fetching limited song details (Title, Artist, Album if available).
Processing 457 raw song entries...
Successfully processed 457 songs for LLM input.

--- New Playlist Details ---
Enter the title for your new sub-playlist: Workout Energizers
Enter a detailed description for the playlist (e.g., 'Upbeat electronic for coding', 'Melancholic acoustic for a rainy day') (optional, press Enter to skip): High-energy tracks for intense workouts
List desired genre(s), comma-separated (e.g., 'synthwave, retrowave, electronic') (optional): electronic, hip-hop, rock
List preferred artist(s), comma-separated (e.g., 'The Midnight, Carpenter Brut') (optional): Eminem, Foo Fighters
Describe the desired mood(s)/vibe(s), comma-separated (e.g., 'energetic, nostalgic, focused') (optional): energetic, intense, motivational
Any other keywords, comma-separated (e.g., '80s, instrumental, driving beat') (optional): workout, gym, running

Playlist criteria captured.

Asking AI to select songs for the new playlist: 'Workout Energizers' based on detailed criteria...
```

## ⚙️ Configuration Options

You can customize behavior by editing constants at the top of the script:
- `SONG_ADD_BATCH_SIZE`: Number of songs to add at once (default: 25)
- `MAX_ADD_RETRIES`: Maximum retry attempts for adding songs (default: 3)
- `FUZZY_MATCH_THRESHOLD`: How strict the song matching should be (default: 65)
- `LLM_TEMPERATURE`: Controls AI creativity level (default: 0.20)

**Advanced Options:**
- Turn on `FETCH_FULL_SONG_DETAILS = True` for even more accurate matching (slower but more precise)
- Adjust `limit` parameters to specify the number of songs or playlists to check

## 🐛 Troubleshooting

- **API Rate Limits**: If you encounter rate limiting, try waiting a few hours before using the tool again
- **Authentication Issues**: Ensure your headers_auth.json file is up-to-date; YouTube Music occasionally requires re-authentication
- **Song Matching Problems**: Try increasing the `FUZZY_MATCH_THRESHOLD` for stricter matching

## 🤝 Contributing

Contributions are welcome! 

## 🙏 Acknowledgments

- [YTMusicAPI](https://ytmusicapi.readthedocs.io/) for YouTube Music integration
- Google's Gemini AI for intelligent song analysis
- [FuzzyWuzzy](https://github.com/seatgeek/fuzzywuzzy) for string matching algorithms

## 📄 License

This project is licensed under the Apache-2.0 license - see the LICENSE file for details.

---


