# AutoTube - Batch PDF to YouTube Video Automator

This repository contains a full serverless pipeline using GitHub Actions and GitHub Pages to automate the conversion of PDF presentations into YouTube videos with AI voiceovers.

## Features
- **Frontend Panel**: Upload multiple PDFs to Google Drive directly from your browser in a single batch.
- **Backend (GitHub Actions)**:
  - Downloads PDFs securely using ID parameters.
  - Extracts text and renders images using PyMuPDF.
  - Generates SEO-optimized scripts, titles, tags, and descriptions using KoboiLLM/LiteLLM proxy.
  - Converts text to speech using Microsoft Edge TTS (Indonesian Voice - `id-ID-ArdiNeural`).
  - Renders the final video using MoviePy (24 FPS, AAC audio).
  - Automatically uploads to YouTube via API in private mode for manual review.

## Setup Instructions

### 1. GitHub Repository Secrets
Go to your repository **Settings > Secrets and variables > Actions** and add the following repository secrets:
- `KOBOI_API_KEY`: Your LiteLLM/Koboi API key for AI script generation.
- `YOUTUBE_CLIENT_SECRET`: The JSON content of your Google Cloud OAuth/Service Account credentials authorized for the YouTube Data API v3.
- `GDRIVE_CREDENTIALS`: The JSON content of your Google Service Account credentials to download files from Google Drive in the backend.

### 2. Frontend Configuration
The frontend is hosted via GitHub Pages from the `docs/` folder.
1. Go to **Settings > Pages** and set the source to deploy from the `docs` folder on the `main` branch.
2. In your Google Cloud Console, create a Web Application OAuth Client ID. Add your GitHub Pages URL to the **Authorized JavaScript origins**.
3. When using the app, input your Google Client ID, GitHub Repository (e.g., `username/repo`), and a GitHub Personal Access Token (PAT) with `repo` and `workflow` permissions to trigger the action.

## Usage
1. Open your GitHub Pages URL (e.g. `https://username.github.io/repo-name/`).
2. Enter your Google Client ID, Repo Name, PAT, and Focus SEO Keyword.
3. Select one or more PDF presentations.
4. Click **Start Automation**. The app will upload the PDFs to your Drive and trigger the GitHub Action in the background. Check your Actions tab to monitor the rendering and upload progress!

## Dependencies
- PyMuPDF
- OpenAI (Compatible LLM Client)
- Edge-TTS
- MoviePy
- Google API Python Client
