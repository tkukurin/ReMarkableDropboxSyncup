
# RmDropbox

It's annoying that ReMarkable uploads docs to the root Dropbox folder.
This is supposed to emulate some 2-way sync by either "symlinking" in the cloud
or literally moving files around.


## Install

Just a dev app with zero dependencies. Run `make install` from the root folder.
Add a `~/.apikeys.json` [access token](https://www.dropbox.com/developers/apps/info/):
```json
{ "dropbox_access_token": "access_token_from_app_console" }
```

Then the app is runnable from the command line via `tkdbox`.
Set alternate config path using `tkdbox --cfg [my_path]`.

