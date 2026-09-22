'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';
import type { ProjectRead } from '@/lib/bidpilot-api';

export function ProjectPicker({
  projects,
  value,
  onChange
}: {
  projects: ProjectRead[];
  value: string;
  onChange: (value: string) => void;
}) {
  const selectedProject = projects.find((project) => project.id === value);
  return (
    <Select value={value || null} onValueChange={(next) => onChange(next ?? '')}>
      <SelectTrigger className='w-full sm:w-80' aria-label='选择项目'>
        <SelectValue placeholder='选择项目'>{selectedProject?.name ?? '选择项目'}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {projects.map((project) => (
          <SelectItem key={project.id} value={project.id}>
            {project.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
