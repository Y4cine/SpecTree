#title[A "simple" editor for writing functional specifications.]

Two serialisation formats: JSON (or YAML) and SQLite.

GUI (tkinter or PyQt - my past experience was that PyQt provides a more modern look and feel, while tkinter is simpler and more lightweight. Qt would only make sense if a more complex GUI is required, otherwise tkinter is sufficient).
Left Tree view of the specification.
Right pane for editing the selected item.

The specs for an item include:
- ID
- parentID (in case of SQLite, not required for JSON/YAML)
- sortKey (for ordering items within the same parent)
- Name
- Title
- Description
- DescriptionType (e.g., plain text, Markdown, HTML, etc.)
- Image (either file pather or base64-encoded string)
- ScreenshotCoordinates (for marking specific areas in the P&ID, if applicable)
- Sensors (tags, descriptions, functions, remarks, etc.)
- Actuators (tags, descriptions, functions, remarks, etc.)
- Remarks (internal notes, not part of the specification)
- References (URLs, documents, etc.)
- SubItems (for JSON/YAML, this is a list of child items; for SQLite, this is determined by querying for items with parentID equal to the current item's ID)
- Version
- Tags (for categorisation and filtering)
- Status (e.g., Draft, Approved, Deprecated)
- Author
- LastModified (timestamp of the last modification)
- ChangeHistory (list of changes with timestamps and descriptions)
- RelatedItems (list of IDs of related items, for cross-referencing)
- CustomFields (a dictionary for any additional fields that may be needed)
- Printable (boolean indicating if the item should be included in printed reports)

The serialisation shall also include metadata about the specification itself, such as:
- Client
- ProjectName
- ProjectNumber
- BOM (Bill of Materials)
- Version
- Author
- LastModified (timestamp of the last modification)
- ChangeHistory (list of changes with timestamps and descriptions)

In case of SQLite, the data will be stored in a single table with columns corresponding to the fields mentioned above. The hierarchy will be maintained using the parentID and sortKey fields.

In case of JSON/YAML, the data will be stored in a nested structure, where each item can contain a list of sub-items. The hierarchy will be maintained through the nesting of items.

Functionality:
- Create, read, update, and delete items and branches in the hierarchy.
- Move items within the hierarchy (change parentID and sortKey).
- The app can be opened in multiple instances, allowing users to work on different specifications simultaneously. Copy-Paste and Drag-and-Drop functionality for moving items between instances.
- Search and filter items based on various criteria (e.g., tags, status, author).
- Export and import specifications in JSON/YAML format.
- Generate reports (e.g., Markdown, Typst, QMD (Quarto)) based on the specifications.

- Version control will be implemented by Git, on file level for JSON/YAML and on record level for SQLite. Each change will be committed with a message describing the change, and the history of changes can be viewed within the app.

== Commands
Commands shall be accessible via Menus, Toolbars, Context Menus, and Shortcuts. The app will have a command pattern implementation to handle user actions and ensure a consistent user experience. 
---

== COM-Connection to the P&ID
The app will have a COM interface to allow integration with the P&ID software. This will enable users to link items in the specification directly to elements in the P&ID, such as sensors and actuators. The COM interface will allow for:
- Retrieving information about elements in the P&ID (e.g., tags, descriptions, functions).

== Exporting to Markdown, Typst, QMD (Quarto)
The app will have functionality to export the specifications to various formats for documentation purposes. This will include:
- Markdown: A simple text format that can be easily converted to HTML or PDF.
- Typst: A modern typesetting system that allows for more complex layouts and styling.
- QMD (Quarto): A format used for creating dynamic documents that can include code and data visualizations.
The publishing step will be carried outside of the app, using the respective tools for each format. The app will generate the necessary files and instructions for publishing the specifications in the desired format.

But there should be an option to trigger the publishing process directly from the app, which would call the respective command-line tools for each format (e.g., pandoc for Markdown, typst for Typst, quarto for QMD) to generate the final output.

The main product shall be a PDF, but the app will also allow users to generate HTML versions of the specifications for interactive viewing.

== Working on nodes
When working on nodes in the specification, users will have the ability to:
- Merge or split nodes to better organize the hierarchy. The hierarchy will be translated in the approriate outline format for the respective export format (e.g., Markdown, Typst, QMD). In case the item has sub-items or filled out fields, then the split operation will create a new item with the same content as the original item, and the user can then edit the content of the new item as needed. The merge operation will combine the content of two items into a single item, and the user can then edit the combined content as needed.

== Working on the SSOT (Single Source of Truth)
The app shall be so easy to use that colleagues will prefer to work on the specification directly in the app, rather than using external tools like Excel or Word. This will ensure that the specification remains up-to-date and consistent, as all changes will be made in a single source of truth. The app will also have features to facilitate collaboration, such as commenting and notifications for changes made by other users.

From this perspective, the app shall be designed to accept several remarks and comments, which are not part of the specification itself, but are meant for internal communication and collaboration. These remarks can be used to provide feedback, ask questions, or discuss specific items in the specification without affecting the actual content of the specification. The app will have a dedicated section for remarks, where users can view and manage their comments and discussions related to the specification.