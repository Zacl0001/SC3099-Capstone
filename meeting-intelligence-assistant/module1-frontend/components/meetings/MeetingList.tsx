import type { Meeting } from '@/lib/types';
import MeetingCard from './MeetingCard';

export default function MeetingList({ meetings }: { meetings: Meeting[] }) {
  return (
    <ul className="space-y-3">
      {meetings.map((meeting) => (
        <li key={meeting.id}>
          <MeetingCard meeting={meeting} />
        </li>
      ))}
    </ul>
  );
}
