# 🍪 Coffie-Stealer

> **Educational Security Research Project**

---

## ⚠️ Important Legal Notice

This project is strictly for **educational and security research purposes only**.

Unauthorized access to computer systems, data theft, or any malicious use of this software is illegal and punishable by law.

The author assumes **zero liability** for misuse of this code. By using this repository, you agree to use it only in environments where you have explicit permission (e.g., your own devices, laboratory environments, or authorized penetration testing engagements).

**DO NOT USE THIS ON SYSTEMS YOU DO NOT OWN OR HAVE WRITTEN PERMISSION TO TEST.**

---

## 📚 Table of Contents

* [Overview](#-overview)
* [Features](#-features)
* [How It Works](#-how-it-works)
* [Installation](#-installation)
* [Configuration](#-configuration)
* [Usage](#-usage)
* [Technical Details](#-technical-details)
* [Detection & Prevention](#-detection--prevention)
* [Disclaimer](#-disclaimer)
* [License](#-license)
* [Contributing](#-contributing)

---

## 📖 Overview

Coffie-Stealer is a Python-based information-gathering tool designed to demonstrate techniques commonly used by credential stealers, browser data extractors, and persistence mechanisms.

It is intended to help security professionals, students, and researchers understand:

* How malware exfiltrates sensitive information.
* How persistence mechanisms are implemented.
* How anti-analysis and VM detection techniques work.
* How collected information can be packaged and transmitted.

> **Note:** The code has been redacted. Any remote server URLs, authentication tokens, or deployment endpoints have been removed.

---

## ✨ Features

### 🎯 Data Collection

| Category            | Description                                                                                   |
| ------------------- | --------------------------------------------------------------------------------------------- |
| Browser Credentials | Extracts saved passwords, cookies, and payment data from Chromium-based browsers and Firefox. |
| Discord Tokens      | Scans local storage for authentication tokens.                                                |
| Steam Data          | Collects Steam Guard files and configuration data.                                            |
| Crypto Wallets      | Extracts data from supported cryptocurrency wallets.                                          |
| System Information  | Collects hostname, public IP, OS, CPU, GPU, and RAM information.                              |
| File Grabbing       | Searches common user directories for selected file extensions.                                |
| Screenshot Capture  | Captures desktop screenshots using Python imaging libraries.                                  |

---

### 🛡️ Evasion & Anti-Analysis

* Virtual Machine detection
* Sandbox environment checks
* Registry execution flags
* Self-deletion mechanisms
* Timing-based analysis detection

---

### 🔒 Persistence & Deployment

* Registry Run key persistence
* Scheduled task creation
* Startup folder execution
* Removable drive propagation
* Network share propagation
* Deployment to common application directories

---

### 📦 Data Packaging & Transmission

* ZIP archive generation
* Multipart HTTP uploads
* Structured reporting and summaries

---

## ⚙️ How It Works

1. Collects system and application data.
2. Processes and organizes gathered information.
3. Packages collected data into compressed archives.
4. Transmits results to a configured testing endpoint.
5. Optionally establishes persistence mechanisms for demonstration purposes.

---


---

## 🔧 Configuration

Before running the project:

1. Configure your own testing environment.
2. Replace placeholder endpoints with authorized laboratory infrastructure.
3. Review all modules and ensure compliance with local laws and organizational policies.

---

## ▶️ Usage

```bash
Figure it out yourself
```

For research environments only.

---

## 🔬 Technical Details

### Supported Platforms

* Windows 10
* Windows 11

### Technologies Used

* Python 3.x
* SQLite
* Windows Registry APIs
* HTTP Requests
* ZIP Compression

---

## 🛡️ Detection & Prevention

Security teams can defend against similar threats by:

* Using endpoint detection and response (EDR) solutions.
* Monitoring browser credential access.
* Restricting unauthorized persistence mechanisms.
* Auditing startup locations and scheduled tasks.
* Monitoring outbound data transfers.

---

## ⚠️ Disclaimer

This repository is provided for educational and research purposes only.

The author does not encourage, support, or condone unauthorized access, credential theft, malware deployment, or any illegal activity.

Users are solely responsible for complying with applicable laws and regulations.

---

## 📄 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.

---

## 🤝 Contributing

Contributions that improve documentation, research value, and defensive security education are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Open a pull request.

---

### ⭐ Support

If this project helps your research or learning process, consider giving the repository a star.
