Non-technical bullet point summary of how the XYZCare system works:

**Overall Flow:**
- Voice-controlled web app for repair technicians to quickly find information in product manuals
- Users speak → system understands → shows relevant content cards

**Step-by-Step Process:**
1. **Voice Input**: User clicks microphone and speaks (e.g., "Pixel 9 Pro manual")
2. **Speech Recognition**: System converts speech to text using AI
3. **Manual Matching**: System finds the right manual using database queries and fuzzy matching
4. **Content Display**: Manual information loads and displays as cards
5. **Question Answering**: User asks specific questions → system finds relevant content using smart search
6. **Card Display**: System shows content cards with page numbers and snippets

**Key Technologies:**
- Local speech-to-text (no internet needed for voice conversion)
- AI-powered semantic search (understands meaning, not just keywords)
- PostgreSQL database for content storage and retrieval
- Modern web interface with card-based content display
- Real-time feedback and logging

The system helps repair technicians find information faster by eliminating manual searching through manuals and providing relevant content in easy-to-read cards.
