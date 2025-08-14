# Overview

This is a Facebook Video Downloader web application built with Flask that attempts to download Facebook videos by providing the video URL. The application provides a clean, dark-themed interface where users can paste Facebook video URLs and attempt downloads. Due to Facebook's enhanced security measures implemented in 2024-2025, most video downloads are blocked by Facebook's protection systems, though video information (titles, metadata) can still be extracted successfully. The system uses the latest yt-dlp library with multiple fallback strategies and includes features like progress tracking, file cleanup, and comprehensive error handling.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
The application uses a traditional server-side rendered approach with Flask templates and Bootstrap for styling:

- **Template Engine**: Jinja2 templates with a base template structure for consistent layout
- **UI Framework**: Bootstrap 5 with dark theme for modern, responsive design
- **Client-side Logic**: Vanilla JavaScript for form validation and user interactions
- **Styling**: Custom CSS combined with Bootstrap classes and Font Awesome icons

## Backend Architecture
The backend follows a simple Flask web application pattern:

- **Web Framework**: Flask with proxy fix middleware for deployment compatibility
- **Download Processing**: yt-dlp library for video extraction and downloading
- **Threading**: Uses Python threading for handling concurrent downloads
- **File Management**: Local file system storage in a downloads directory
- **Session Management**: Flask sessions with secret key configuration

## Core Features
- **URL Validation**: Client and server-side validation for Facebook URLs
- **Quality Selection**: Multiple video quality options (best, 720p, 480p, 360p, worst)
- **Progress Tracking**: Global downloads status tracking with thread-safe operations
- **File Cleanup**: Automatic cleanup of files older than 1 hour
- **Error Handling**: Comprehensive error handling with user-friendly flash messages

## Design Patterns
- **MVC Pattern**: Separation of concerns with templates (views), Flask routes (controllers), and data processing logic
- **Thread-Safe Operations**: Uses threading locks for managing download status
- **Utility Functions**: Modular helper functions for URL validation and file cleanup

# External Dependencies

## Core Libraries
- **Flask**: Web application framework for routing and templating
- **yt-dlp**: Video downloading library for extracting Facebook videos
- **Werkzeug**: WSGI utilities including ProxyFix middleware

## Frontend Dependencies
- **Bootstrap 5**: CSS framework loaded via CDN with dark theme
- **Font Awesome**: Icon library for UI elements
- **Custom CSS/JS**: Local static assets for application-specific styling and functionality

## System Requirements
- **Python Environment**: Requires Python with Flask and yt-dlp packages
- **File System**: Local storage for temporary video downloads
- **Threading Support**: Uses Python's threading module for concurrent operations

## Deployment Considerations
- **ProxyFix Middleware**: Configured for deployment behind reverse proxies
- **Environment Variables**: Uses SESSION_SECRET environment variable for security
- **Static File Serving**: Serves CSS, JS, and downloaded files through Flask