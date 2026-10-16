import EmptyState from '@/components/common/EmptyState';
import { ListIcon } from '@/components/common/Icons';
import type { ActionItem } from '@/lib/types';
import ActionItemCard from './ActionItemCard';

interface ActionItemListProps {
  items: ActionItem[];
  onViewSource?: (item: ActionItem) => void;
}

export default function ActionItemList({ items, onViewSource }: ActionItemListProps) {
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<ListIcon />}
        title="No action items found"
        description="No follow-up tasks were identified in this meeting."
      />
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.id}>
          <ActionItemCard item={item} onViewSource={onViewSource} />
        </li>
      ))}
    </ul>
  );
}
