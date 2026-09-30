# COSC-4353-QueueSmart
Project for COSC 4353

## Admin UI

Open `admin.html` through a local static server (for example, `python3 -m http.server 8000`), then visit `http://localhost:8000/admin.html`.

- **Overview:** service list, queue counts, and open/close controls.
- **Services:** create and edit a name (required, up to 100 characters), description (required), positive whole-minute duration, and low/medium/high priority.
- **Queues:** select a service, move students up/down, remove students, and simulate serving the next student. Closed queues cannot serve students.

This is a standalone admin UI demo, not authentication. It sets `window.currentUser.role` to `staff` and uses sample queues in memory; reloading resets services and queues. The existing login mock is unchanged. When integrating real login, replace the demo role assignment with the authenticated user.

### Notification integration

`admin.html` loads `css/notifications.css`, provides `#bell-mount`, and loads `js/notifications.js` before `js/admin.js`, which calls `initNotifications()`.

Admin actions call the existing `notify('student', message, type)` API with actual service names:

| Action | Type | Message |
| --- | --- | --- |
| Open occupied queue | info | `{service} queue is now open` |
| Close occupied queue | warning | `{service} queue is now closed` |
| Change a student's position | info | `You moved to position {position} in {service}` |
| A new student reaches the front of an open queue, or an occupied queue opens | warning | `You're next for {service}, please head to the help desk` |
| Serve next | success | `You've been served for {service}` |
| Remove student | error | `You were removed from the {service} queue` |

Position messages are emitted for every affected remaining student. Queue status messages are emitted once for occupied queues. Rendering alone does not generate notifications. Student join/leave actions belong to the student screens and are not simulated here. Creating/editing services is outside the supplied event table and only shows local confirmation.

**Team integration limitation:** the supplied notification API stores messages by role, not by student or service membership. As a result, individual position/served/removed messages cannot yet be delivered privately to the intended student. The teammate's notification module needs recipient identifiers for that. The admin bell shows staff notifications, so student-targeted notifications from these actions do not appear in it. Notifications retain the module's existing local-storage persistence even though admin demo data resets on reload.
