# PolicyAnalyzer-Agent

This is a rough draft of policy analyzer for open source official policies, regulations, and laws. Based on LangChain structure and Streamlit UI.

## How to Run

To start the application and automatically set up the environment:

1. Open PowerShell in this directory.
2. Run the startup script:

   ```powershell
   .\run.ps1
   ```

This script will:

- Activate the virtual environment (`venv`).
- Set required environment variables (like `USER_AGENT`) to suppress warnings.
- Launch the Streamlit app correctly using `streamlit run`.
