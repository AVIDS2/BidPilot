'use client';

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/components/ui/breadcrumb';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Fragment } from 'react';

const LABELS: Record<string, string> = {
  dashboard: '总览',
  projects: '项目',
  agent: '助手',
  knowledge: '知识库',
  requirements: '需求清单',
  runs: '运行记录',
  deliverables: '交付物',
  reviews: '评审',
  members: '团队成员',
  account: '账户',
  settings: '设置',
  providers: '模型与运行时',
  webhooks: 'Webhooks'
};

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 0) return null;

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {segments.map((segment, index) => {
          const href = `/${segments.slice(0, index + 1).join('/')}`;
          const title = LABELS[segment] || (index === segments.length - 1 ? '详情' : segment);
          const isLast = index === segments.length - 1;
          return (
            <Fragment key={href}>
              {!isLast && (
                <>
                  <BreadcrumbItem className='hidden md:block'>
                    <BreadcrumbLink render={<Link href={href}>{title}</Link>} />
                  </BreadcrumbItem>
                  <BreadcrumbSeparator className='hidden md:block' />
                </>
              )}
              {isLast && (
                <BreadcrumbItem>
                  <BreadcrumbPage>{title}</BreadcrumbPage>
                </BreadcrumbItem>
              )}
            </Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
