'use client';

import { useMemo } from 'react';
import type { NavGroup, NavItem } from '@/types';

export function useFilteredNavItems(items: NavItem[]) {
  return useMemo(() => items, [items]);
}

export function useFilteredNavGroups(groups: NavGroup[]) {
  const items = useFilteredNavItems(groups.flatMap((group) => group.items));
  return useMemo(
    () =>
      groups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) =>
            items.some((candidate) => candidate.title === item.title)
          )
        }))
        .filter((group) => group.items.length > 0),
    [groups, items]
  );
}
