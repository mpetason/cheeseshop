from lxml import html
import requests
import argparse
import os
import rarfile
import datetime
import hashlib


results_url = "https://www.hltv.org/results?team="
base_url = "https://www.hltv.org"


class Scraper:
    def __init__(self, output_dir, team, replays, upload_url,
                 _list=False, _download=False, extract=False, upload=False):
        self.directory = output_dir
        self.team = team
        self.replay_count = replays
        self.upload_url = upload_url
        self.replay_list = _list
        self.download = _download
        self.extract = extract
        self.upload = upload
        self.matches = []
        if self.download or self.replay_list:
            self.matches = self.get_match(self.team)[:self.replay_count]

    def run(self):
        for match in self.matches:
            if self.replay_list:
                self._list(match)

            if self.download:
                self._download(match)

        if self.extract:
            self.extract_replays()

        if self.upload:
            self.upload_replay()

    def _download(self, match):
        """ Runs a dupe check on the match to make sure it hasn't already been
            downloaded. Verifies if the match has a demo file, if not it will
            skip downloading, otherwise it will call download_replay() to
            download the replay file.
        """
        match_filename = match.split('/')[-1]
        if self.dupe_check_replays(match_filename):
            print("[Skip] {} has already been downloaded,"
                  "skipping.".format(match_filename))
        else:
            demo_url = self.get_demo_link(self.format_url(match))
            if demo_url:
                print("[Download] Downloading {}...".format(match_filename,))
                self.download_replay(("{}{}".format(base_url, demo_url)),
                                     match, self.format_url(match))
            else:
                print("[Skip] Skipping Download for", match.split('/')[-1],
                      ". Demo file not available yet.")

    def _list(self, match):
        """ Lists matches based on the number of --replays. Prints out date,
            demo file URL, and match title.
        """
        demo_url = self.get_demo_link(self.format_url(match))
        if demo_url:
            match_meta = [self.get_match_date(self.format_url(match)),
                          "{}{}".format(base_url, demo_url),
                          match.split('/')[-1]]
        else:
            match_meta = [self.get_match_date(self.format_url(match)),
                          "No Demo File Yet", match.split('/')[-1]]
        print(match_meta)

    def download_replay(self, demo_url, match, match_url):
        """ Verifies that the --directory exists, if not create it. Downloads
            the demo file to the specified directory.
        """
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        match_date = self.get_match_date(self.format_url(match))
        local_filename = "{}_{}_{}.rar".format(self.team, match_date,
                                               match_url.split('/')[-1])
        local_filename_location = os.path.join(self.directory, local_filename)
        r = requests.get(demo_url)
        with open(local_filename_location, "wb") as replay:
            replay.write(r.content)
        print("[Download] {} has finished download.".format(local_filename))
        print("\n")

    def dupe_check_replays(self, filename):
        """ Checks for downloaded match rar files, then returns true or false.
        """
        replay_file = "{}.rar".format(filename)
        return os.path.isfile(os.path.join(self.directory, replay_file))

    def extract_replays(self):
        """ Extracts all rar files in the specified directory. Skips files
            that have already been extracted.
        """
        for rar in os.listdir(self.directory):
            if not rar.endswith('.rar'):
                continue
            filepath = os.path.join(self.directory, rar)
            opened_rar = rarfile.RarFile(filepath)
            for replay_file in opened_rar.infolist():
                if os.path.isfile(os.path.join(self.directory,
                                  replay_file.filename)):
                    print("[Extract] {} already extracted, skipping.".format(
                          replay_file.filename))
                else:
                    print("[Extract] Extracting "
                          "{}.".format(replay_file.filename))
                    opened_rar.extract(member=replay_file,
                                       path=self.directory)

    def format_url(self, match, base_url="https://www.hltv.org"):
        """ Formats the URL based on the base_url and match path. """
        formatted_url = '{}/{}'.format(base_url, match)
        return formatted_url

    def get_demo_link(self, url):
        """ Get demo links to download the replays. This returns the download
            link for the demo files.
        """
        page = requests.get(url)
        tree = html.fromstring(page.content)
        demo_links = tree.xpath('//a[contains(@href, "/download/demo")]/@href')
        return demo_links[0] if demo_links else None

    def get_match(self, team_id):
        """ Get matches based on the URL and Team ID. This returns the match
            results link.
        """
        fixed_team_url = "{}{}".format(results_url, team_id)
        page = requests.get(fixed_team_url)
        tree = html.fromstring(page.content)
        match_links = tree.xpath('//a[contains(@href, "/matches/")]/@href')
        return match_links

    def get_match_date(self, url):
        """ Get Unix timestamp from a specific match and convert it to readable
            date.
        """
        match_page = requests.get(url)
        match_tree = html.fromstring(match_page.content)
        match_date = match_tree.xpath('//div[@class="date"]/@data-unix')
        match_timestamp = datetime.datetime.fromtimestamp(
            int(match_date[0]) / 1000.0).strftime('%Y-%m-%d')
        return match_timestamp

    def upload_replay(self):
        """ Upload replay files in specified dirctory. """
        demo_hash = hashlib.sha1()
        for dem in os.listdir(self.directory):
            if not dem.endswith('.dem'):
                continue
            filepath = os.path.join(self.directory, dem)
            with open(filepath, "rb") as demo:
                chunk = 0
                while chunk != b'':
                    chunk = demo.read(1024)
                    demo_hash.update(chunk)
                print("[Check] if {} already exists.".format(dem))
                r = requests.post(self.upload_url,
                                  data={'game': 'cs:go',
                                        'replay_sha1sum':
                                        demo_hash.hexdigest()
                                        })
                if r.text == "Replay sha1 already exists":
                    temp_url = ""
                    print("[Skip] {}. {}.".format(dem, r.text))
                else:
                    temp_url = r.json()['tempurl']
                    print("[Tempurl] Swift tempurl created for"
                          "{}.".format(dem))
                demo_file = {'upload_file': open(filepath, "rb")}
                if not temp_url == "":
                    print("[Upload] Uploading {} to swift.".format(dem))
                    upload = requests.put(temp_url, files=demo_file)
                    if upload.status_code == 201:
                        print("[Upload] Upload for {} succeeded.".format(dem))
                        print("\n")
                    else:
                        print("[Upload] Upload for {} was not"
                              "successful.".format(dem))
                        print("[Error] {}".format(upload.status_code))
                        print("\n")


def main():
    parser = argparse.ArgumentParser(description='hltv scraper')
    parser.add_argument('--download', action='store_true',
                        help='Download replay files.')
    parser.add_argument('--extract', action='store_true',
                        help='Extract replay files.')
    parser.add_argument('--list', action='store_true',
                        help='List match details.')
    parser.add_argument('--directory', action="store", required=True,
                        help='Specify custom output directory to store replay'
                             ' files. Can also be used with --extract when'
                             ' extracting already downloaded replays.')
    parser.add_argument('--replays', type=int, default=1,
                        help='Number of replays to download.')
    parser.add_argument('--team',
                        help='Team UUID for hltv.org.')
    parser.add_argument('--upload', action='store_true',
                        help="Upload files to swift.")
    parser.add_argument('--upload_url', action='store',
                        help="URL for uploading.")
    args = parser.parse_args()

    if not (args.team or args.extract or args.upload):
        parser.error('Please use --team to specify the team, or --extract if '
                     'extracting from directory, or --upload if uploading.')

    team = args.team

    scraper = Scraper(args.directory, team, args.replays, args.upload_url,
                      args.list, args.download, args.extract, args.upload)
    scraper.run()
