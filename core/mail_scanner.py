# ==========================================================
# FC Utilities - Mail Scanner
# ----------------------------------------------------------
# Purpose:
# Discover communication profiles and mailboxes.
#
# Author: Minette & James
# Version: 3.0
# ==========================================================

from pathlib import Path
import configparser

from core.mailbox import Mailbox


class MailScanner:

    def __init__(self):

        self.profiles = []
        self.mailboxes = []
        self.accounts = {}

    # ------------------------------------------------------
    # Find Profiles
    # ------------------------------------------------------

    def find_profiles(self):

        self.profiles.clear()

        thunderbird = Path.home() / "AppData" / "Roaming" / "Thunderbird"

        profiles_folder = thunderbird / "Profiles"
        profiles_ini = thunderbird / "profiles.ini"

        self.active_profile = None

        if profiles_ini.exists():

            config = configparser.ConfigParser()
            config.read(profiles_ini)

            for section in config.sections():

                if section.startswith("Install"):

                    default_path = config.get(section, "Default", fallback="")

                    if default_path:

                        self.active_profile = Path(default_path).name

                        break

            if self.active_profile is None:

                for section in config.sections():

                    if (
                        config.has_option(
                            section,
                            "Default",
                        )
                        and config.get(
                            section,
                            "Default",
                        )
                        == "1"
                    ):

                        profile_path = config.get(section, "Path", fallback="")

                        self.active_profile = Path(profile_path).name

                        break

        if not profiles_folder.exists():

            return []

        for profile in profiles_folder.iterdir():

            if profile.is_dir():

                self.profiles.append(
                    {
                        "active": (profile.name == self.active_profile),
                        "name": profile.name,
                        "path": profile,
                        "mail": profile / "Mail",
                        "imap": profile / "ImapMail",
                    }
                )

        return self.profiles

    # ------------------------------------------------------
    # Profile Count
    # ------------------------------------------------------

    def profile_count(self):

        return len(self.profiles)

    # ------------------------------------------------------
    # Read Accounts
    # ------------------------------------------------------

    def read_accounts(self):

        self.accounts.clear()

        for profile in self.profiles:

            prefs = profile["path"] / "prefs.js"

            if not prefs.exists():

                continue

            current_folder = None

            with open(
                prefs,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as file:

                for line in file:

                    if ".directory" in line and "ImapMail" in line:

                        current_folder = (
                            line.split("ImapMail/")[-1].replace('");', "").strip()
                        )

                    elif ".name" in line and "@" in line and current_folder:

                        email = line.split('"')[-2]

                        self.accounts.setdefault(current_folder, [])

                        self.accounts[current_folder].append(email)

                        current_folder = None

        return self.accounts

    # ------------------------------------------------------
    # Scan Mail Store
    # ------------------------------------------------------

    def scan(self, profile):

        self.mailboxes.clear()

        folders = [
            ("Thunderbird", Path(profile["mail"])),
            ("Thunderbird", Path(profile["imap"])),
        ]

        for source, root in folders:

            if not root.exists():

                continue

            for file in root.rglob("*"):

                if (
                    not file.is_file()
                    or file.suffix != ""
                    or file.name.endswith(".msf")
                ):

                    continue

                try:

                    relative_path_obj = file.relative_to(root)

                    path_parts = relative_path_obj.parts

                    if len(path_parts) > 1:
                        server = path_parts[0]
                        relative_path = str(Path(*path_parts[1:]))
                    else:
                        server = path_parts[0]
                        relative_path = path_parts[0]

                    relative_path = relative_path.replace(
                        "INBOX",
                        "Inbox",
                    )
                    relative_path = relative_path.replace(".sbd", "")
                    relative_path = relative_path.replace("\\", " / ")
                    relative_path = relative_path.replace("/", " / ")
                    display_name = relative_path.replace("/", " / ")

                    mailbox = Mailbox(
                        id=str(file),
                        name=display_name,
                        source=source,
                        parent=self.accounts.get(
                            server,
                            [],
                        ),
                        relative_path=relative_path,
                        full_path=str(file),
                        size=file.stat().st_size,
                        empty=file.stat().st_size == 0,
                    )
                    self.mailboxes.append(mailbox)

                except Exception:

                    pass

        self.mailboxes.sort(
            key=lambda mailbox: (
                mailbox.empty,
                mailbox.display_name.lower(),
            )
        )

        return self.mailboxes

    # ------------------------------------------------------
    # Mailbox Count
    # ------------------------------------------------------

    def mailbox_count(self):

        return len(self.mailboxes)
