'use client';

import AppSidebar from '@/components/layout/app-sidebar';
import Header from '@/components/layout/header';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { AuthGuard } from '@/components/auth/auth-guard';

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <SidebarProvider defaultOpen>
        <AppSidebar />
        <SidebarInset className='min-h-svh min-w-0'>
          <Header />
          <div className='flex min-h-0 flex-1 flex-col'>{children}</div>
        </SidebarInset>
      </SidebarProvider>
    </AuthGuard>
  );
}
