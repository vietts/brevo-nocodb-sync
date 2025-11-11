# Brevo ↔ NocoDB Sync

Automated synchronization system that imports email campaign data from [Brevo](https://www.brevo.com/) and syncs it to a [NocoDB](https://nocodb.com/) database. Perfect for tracking campaign metrics and maintaining a centralized database of your email marketing performance.

## Features

- **🚀 Automated Daily Sync**: Runs automatically every day at 9 AM using launchd (macOS)
- **🎯 Smart Filtering**: Only syncs new campaigns and those not in "Sent" state to save API calls
- **📊 Comprehensive Metrics**: Imports delivery stats, open rates, click rates, bounces, and more
- **🔐 Secure Configuration**: API keys stored in environment variables, not in version control
- **📝 Detailed Logging**: Complete execution logs with success/failure status indicators
- **⚡ Efficient Deduplication**: Checks existing campaigns to avoid reprocessing
- **🔄 Update Support**: Re-syncs campaigns that are still in progress

## What Gets Synced

The script extracts the following data from Brevo campaigns:

- Campaign ID and name
- Creation and send dates
- Campaign status (Draft, Scheduled, Sending, Sent, etc.)
- Delivery metrics (sent, delivered, bounces)
- Engagement metrics (unique opens, unique clicks)
- Open and click rates (calculated as percentages)
- Campaign URL and notes

## Prerequisites

- Python 3.7+
- Active [Brevo](https://www.brevo.com/) account with API access
- Active [NocoDB](https://nocodb.com/) account with a database
- macOS (for the included launchd scheduler; adjust scheduling for other OS)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/brevo-nocodb-sync.git
cd brevo-nocodb-sync
```

### 2. Set Up API Keys

Create a `.env` file in the project root with your API credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
BREVO_API_KEY=your_actual_brevo_api_key_here
NOCODB_API_KEY=your_actual_nocodb_api_key_here
```

To get your API keys:

- **Brevo API Key**: Log in to Brevo → Account → API Key
- **NocoDB API Key**: Log in to NocoDB → Account Menu → Tokens → Generate New Token

### 3. Create Configuration File

Copy the example configuration:

```bash
cp brevo-nocodb-config.example.json brevo-nocodb-config.json
```

Edit `brevo-nocodb-config.json` and update:
- `table_id`: Your NocoDB table ID (visible in URL: `.../m91yfxemctv3ufz/...`)
- `base_url`: Your NocoDB base URL
- `output_file`: Where to save CSV exports (if using the CSV script)

The script will use environment variables first, then fall back to the config file values.

### 4. Install Dependencies

```bash
pip install requests
```

## Usage

### Manual Execution

Run the sync script manually:

```bash
python3 brevo-nocodb-sync.py
```

Output will show:
- Number of campaigns found
- New campaigns being synced
- Campaigns being updated
- Success or failure status

### View Logs

Monitor real-time execution logs:

```bash
tail -f /tmp/brevo-nocodb-sync-executions.log
```

Or use the convenience alias (if added to your shell):

```bash
brevo-log
```

### CSV Export (Optional)

Generate a CSV file of all campaigns:

```bash
python3 brevo-campagne.py
```

## Automated Scheduling (macOS)

### Set Up Automatic Daily Sync at 9 AM

1. Create a launchd plist file:

```bash
mkdir -p ~/Library/LaunchAgents
cat > ~/Library/LaunchAgents/com.brevo.nocodb.sync.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.brevo.nocodb.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/YOUR_USERNAME/brevo-nocodb-sync/brevo-nocodb-sync.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/brevo-nocodb-sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/brevo-nocodb-sync-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>BREVO_API_KEY</key>
        <string>YOUR_BREVO_API_KEY</string>
        <key>NOCODB_API_KEY</key>
        <string>YOUR_NOCODB_API_KEY</string>
    </dict>
</dict>
</plist>
EOF
```

2. Update the plist with your username and API keys:
   - Replace `YOUR_USERNAME` with your actual macOS username
   - Replace `YOUR_BREVO_API_KEY` and `YOUR_NOCODB_API_KEY` with your actual keys

3. Load the job:

```bash
launchctl load ~/Library/LaunchAgents/com.brevo.nocodb.sync.plist
```

4. Verify it's running:

```bash
launchctl list | grep brevo
```

5. Check logs:

```bash
tail -f /tmp/brevo-nocodb-sync-executions.log
```

### Unload the Job

If you need to stop the automated syncs:

```bash
launchctl unload ~/Library/LaunchAgents/com.brevo.nocodb.sync.plist
```

## How It Works

### Filtering Logic

The script is smart about what it syncs:

1. **Retrieves** all campaigns from Brevo
2. **Checks** which campaigns already exist in NocoDB (by ID)
3. **Syncs** new campaigns (not in NocoDB yet)
4. **Updates** existing campaigns that are NOT in "Sent" state

This means:
- ✅ New campaigns are always synced
- ✅ In-progress campaigns (Drafts, Scheduled, Sending) are re-synced to update metrics
- ⏭️ Completed campaigns (Sent status) are skipped (metrics won't change)

### Deduplication

The script maintains data integrity by:
- Querying NocoDB for existing campaign IDs on each run
- Using campaign ID as the primary identifier
- Only inserting truly new records
- Avoiding duplicate syncs

### Logging

All executions are logged to `/tmp/brevo-nocodb-sync-executions.log` with:
- Timestamp of execution
- Number of campaigns found
- Number of new campaigns synced
- Number of campaigns updated
- Final status: `STATUS: ✅ OK` or `STATUS: ❌ FALLITO`

Example log entry:
```
2025-11-11 09:00:15,231 - INFO - ════════════════════════════════════════════════════════════════════════════════════
2025-11-11 09:00:15,232 - INFO - 🚀 Avviando sincronizzazione Brevo -> NocoDB
2025-11-11 09:00:17,445 - INFO - ✅ Trovate 12 campagne da Brevo
2025-11-11 09:00:18,123 - INFO - 📥 Nuove campagne da sincronizzare: 3
2025-11-11 09:00:22,891 - INFO - ✨ Sincronizzazione completata con SUCCESSO
2025-11-11 09:00:22,892 - INFO - STATUS: ✅ OK
```

## Troubleshooting

### "Impossibile accedere alla tabella NocoDB"

- Verify your NocoDB API key is correct
- Check that the table ID in config matches your actual NocoDB table
- Ensure the NocoDB table has the expected columns

### "Errore: 401 Unauthorized"

- Check that `BREVO_API_KEY` environment variable is set correctly
- Verify your Brevo API key hasn't expired
- Test your key directly on Brevo's API documentation page

### Script runs but data shows zeros

- Verify the Brevo API is returning data with `?statistics=globalStats` parameter
- Check that campaigns in Brevo actually have delivery metrics
- Draft campaigns won't have statistics; only sent campaigns do

### No output or email errors

- Check `/tmp/brevo-nocodb-sync-error.log` for detailed error messages
- Verify Python 3 is installed: `python3 --version`
- Confirm requests library is installed: `pip list | grep requests`

## Benefits of This Repository

By using version control and GitHub, you gain:

- **📦 Backup**: Your code is safely stored in the cloud
- **🔄 Version History**: Track all changes and revert if needed
- **🤝 Collaboration**: Easily share and collaborate with team members
- **🚀 Deployment**: Quickly set up the system on new machines
- **📊 Monitoring**: Use GitHub's built-in tools for tracking issues
- **🔧 CI/CD**: Opportunity to add automated testing or linting
- **🌟 Community**: Share useful improvements with others

## File Structure

```
brevo-nocodb-sync/
├── brevo-nocodb-sync.py          # Main synchronization script
├── brevo-campagne.py             # CSV export utility
├── brevo-nocodb-config.example.json  # Configuration template
├── .env.example                  # Environment variables template
├── .gitignore                    # Files to exclude from version control
├── README.md                     # This file
└── LICENSE                       # Project license
```

## Security Notes

⚠️ **Important**:

- **Never commit** `.env` or `brevo-nocodb-config.json` to version control
- **Never share** your API keys or paste them in public issues
- Use `.env.example` and `brevo-nocodb-config.example.json` as templates
- Rotate your API keys periodically
- If you accidentally commit secrets, invalidate them immediately and generate new ones

## API Reference

### Brevo API
- Documentation: https://developers.brevo.com/
- Endpoint: `GET /emailCampaigns` with `?statistics=globalStats`
- Rate limits: Check Brevo documentation for current limits

### NocoDB API
- Documentation: https://docs.nocodb.com/
- Endpoint: `GET/POST /tables/{table_id}/records`
- Authentication: Bearer token in Authorization header

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Found a bug? Have a feature request? Feel free to:
1. Open an issue on GitHub
2. Fork the repository
3. Submit a pull request with improvements

## Support

For issues with:
- **Brevo API**: https://support.brevo.com/
- **NocoDB**: https://community.nocodb.com/
- **This Script**: Check the Troubleshooting section or open a GitHub issue

## Changelog

### v1.0.0 (Initial Release)
- Automated Brevo to NocoDB synchronization
- Smart filtering for new and in-progress campaigns
- Comprehensive logging and status tracking
- macOS launchd scheduler included

---

Made with ❤️ for email marketing automation
