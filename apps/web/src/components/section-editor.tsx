import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import {
  BoldIcon,
  ItalicIcon,
  Heading2Icon,
  Heading3Icon,
  ListIcon,
} from "lucide-react";

interface SectionEditorProps {
  content: string;
  onChange?: (markdown: string) => void;
  readOnly?: boolean;
}

export function SectionEditor({ content, onChange, readOnly = false }: SectionEditorProps) {
  const editor = useEditor({
    extensions: [StarterKit],
    content,
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      onChange?.(editor.getHTML());
    },
  });

  if (!editor) return null;

  return (
    <div className="border rounded-md">
      {!readOnly && (
        <div className="flex gap-1 border-b p-2 bg-muted/50">
          <ToggleGroup variant="outline" size="sm" defaultValue={[]}>
            <ToggleGroupItem
              value="bold"
              aria-label="Bold"
              onClick={() => editor.chain().focus().toggleBold().run()}
            >
              <BoldIcon />
            </ToggleGroupItem>
            <ToggleGroupItem
              value="italic"
              aria-label="Italic"
              onClick={() => editor.chain().focus().toggleItalic().run()}
            >
              <ItalicIcon />
            </ToggleGroupItem>
            <ToggleGroupItem
              value="heading2"
              aria-label="Heading 2"
              onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            >
              <Heading2Icon />
            </ToggleGroupItem>
            <ToggleGroupItem
              value="heading3"
              aria-label="Heading 3"
              onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            >
              <Heading3Icon />
            </ToggleGroupItem>
            <ToggleGroupItem
              value="bulletList"
              aria-label="Bullet list"
              onClick={() => editor.chain().focus().toggleBulletList().run()}
            >
              <ListIcon />
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      )}
      <EditorContent editor={editor} className="prose prose-sm max-w-none p-4 min-h-[200px]" />
    </div>
  );
}
