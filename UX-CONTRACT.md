# Dashboard behavior

The overview opens on the current workspace's last in-session analysis or an
explicit Analyze action. Refresh retains the previous result until success.
Cancellation and failure retain prior results. Only one engine command runs at
a time. File navigation resolves a known source inside the selected workspace.

Search and filtering preserve the current view and never change analysis data.
Empty states distinguish unavailable analysis and zero matching records. All
write actions go through explicit VS Code confirmation. Offline exports present
the same structured model with local file links and downloadable artifacts.
English is the current UI locale. Timestamps use the user's browser locale.
