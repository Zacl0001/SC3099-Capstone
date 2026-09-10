// Purpose: Global application layout.
//
// Put:
//
// global CSS
// navigation
// authentication provider if needed
// page metadata
// Example conceptual structure:
//
// <html>
//   <body>
//     <Navbar />
//     {children}
//   </body>
// </html>


import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SAIV - Secure Attendance System',
  description: 'Student check-in interface with liveness detection',
  manifest: '/manifest.json',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
