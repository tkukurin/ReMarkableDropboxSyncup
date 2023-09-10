
# RmDropbox

Easily upload PDF/paper links to Dropbox, meant to be used with ReMarkable 2.
Additionally tracks papers to a Notion database, if Notion keys provided.
Hacky and barely tested.


## Install

Just a dev app with zero dependencies. Run `make install` from the root folder.
Add a `~/.tkapikeys.json` [access token](https://www.dropbox.com/developers/apps/info/):
```json
{ "dropbox": { "access_token": "access_token_from_app_console" } }
```

Optionally, the api keys file can contain a Notion dependency:
```json
{
  "dropbox": { "access_token": "access_token_from_app_console" },
  "notion": {
    "internal_integration_secret": "secret_asdfasd",
    "pages": {
      "remarkable": "pageid_from_url"
    }
  }
}
```

Then the app is runnable from the command line via `tkdbox`.
Set alternate config path using `tkdbox --cfg [my_path]`.

