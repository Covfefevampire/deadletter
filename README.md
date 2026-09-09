# Dead Letter

Dead Letter is a Python Discord bot for curious words and literary language.

## Features

- `/define word` returns:
  - definition
  - part of speech
  - pronunciation
  - synonyms
  - etymology when the dictionary source provides it
  - an example sentence
- `/wordoftheday` manually posts today's curated entry for testing.
- `/synonym word` returns useful direct synonyms grouped by part of speech when available.
- `/antonym word` returns useful direct antonyms grouped by part of speech when available,
  or clearly says when no true antonym is available.
- `/randomword` returns a curated writing word with its part of speech,
  definition, example, and a scene-writing challenge.
- Posts a curated, literary or unusual Word of the Day every day at 09:00
  America/Detroit in channel `1547049637565964328`.
- Includes the word, pronunciation, part of speech, definition, synonyms,
  etymology when available, and a natural example sentence.
- Persists the posted-word history so automatic posts do not duplicate after
  restarts and do not repeat a word until the curated list is exhausted.
- Uses Wiktionary as the primary dictionary source and Datamuse as a fallback,
  both without an API key.
- Remembers the last post date in `dead_letter_state.json`, so restarts do not
  cause duplicate daily posts.

## Setup

1. Create a Discord application and bot in the Discord Developer Portal.
2. Enable the **applications.commands** scope when generating the invite URL.
3. Invite the bot to a server with permission to:
   - View Channels
   - Send Messages
   - Embed Links
4. Add the token as the `DISCORD_TOKEN` environment variable or Replit Secret.
   The token is intentionally never stored in source code.
5. Install dependencies and start the bot:

   ```bash
   pip install -r requirements.txt
   python main.py
   ```

## Configuration

Copy `.env.example` as a reference. You can set:

- `WORD_OF_DAY_CHANNEL_ID` to choose the destination channel. It defaults to
  `1547049637565964328`.
- `DEAD_LETTER_STATE_PATH` to move the small state file.

The bot uses the `America/Detroit` timezone, including daylight-saving changes,
and requires permission to View Channel, Send Messages, and Embed Links in the
configured channel.