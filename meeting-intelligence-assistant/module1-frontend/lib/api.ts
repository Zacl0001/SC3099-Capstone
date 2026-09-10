// Very important.
//
// Centralize API communication here.
//
// Instead of:
//
// fetch(...)
// being scattered throughout the frontend, create functions such as:
//
// login()
// register()
// getMeetings()
// getMeeting()
// uploadTranscript()
// processMeeting()
// getSummary()
// getActionItems()
// getDecisions()
// askQuestion()
// Conceptually:
//
// export async function askQuestion(
//   meetingId: string,
//   question: string
// ) {
//   // call backend
// }