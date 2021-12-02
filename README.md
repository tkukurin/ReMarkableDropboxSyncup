
# RmDropbox

It's annoying that ReMarkable uploads docs to the root Dropbox folder.
This is supposed to emulate some 2-way sync by either "symlinking" in the cloud
or literally moving files around.


## Running

Just a dev app with zero dependencies.
Add a `keys.json` to the root folder with your [access token](https://www.dropbox.com/developers/apps/info/):
```json
{
  "access_token": "access_token_from_app_console"
}
```

Options via `python src/tkukurin/main.py --help`.
The file header explains running logic.

