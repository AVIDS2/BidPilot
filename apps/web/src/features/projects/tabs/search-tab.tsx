import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { SearchIcon } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { searchKnowledge, type SearchResult } from "@/lib/api";

interface SearchTabProps {
  projectId: string;
}

export function SearchTab({ projectId }: SearchTabProps) {
  const { t } = useTranslation("projects");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const results = await searchKnowledge({ project_id: projectId, query: searchQuery.trim() });
      setSearchResults(results);
    } catch {
      toast.error(t("search.failed"));
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("search.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder={t("search.placeholder")}
              className="pl-9"
            />
          </div>
          <Button onClick={handleSearch} disabled={isSearching || !searchQuery.trim()}>
            {isSearching && <Spinner data-icon="inline-start" />}
            {t("search.search")}
          </Button>
        </div>
        {searchResults.length > 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-sm font-medium">{t("search.results", { count: searchResults.length })}</p>
            {searchResults.map((r) => (
              <div key={r.chunk_id} className="rounded-md border p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <span>{t("search.score", { value: r.score.toFixed(3) })}</span>
                </div>
                <p className="text-sm whitespace-pre-wrap line-clamp-6">{r.content}</p>
              </div>
            ))}
          </div>
        )}
        {searchResults.length === 0 && searchQuery && !isSearching && (
          <Empty className="min-h-32">
            <EmptyHeader>
              <EmptyMedia variant="icon"><SearchIcon /></EmptyMedia>
              <EmptyTitle>{t("search.emptyTitle")}</EmptyTitle>
              <EmptyDescription>{t("search.emptyDesc")}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </CardContent>
    </Card>
  );
}
