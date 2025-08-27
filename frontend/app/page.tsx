'use client';

import HeaderNav from '@/components/HeaderNav';
import { useState } from 'react';
import { Box, Button, Flex, HStack, NumberInput, NumberInputField, Radio, RadioGroup, Stack, Text, Textarea } from '@chakra-ui/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { sampleQueries } from './sampleQueries';

export default function Page() {
  const [query, setQuery] = useState('');
  const [indexChoice, setIndexChoice] = useState<'llm_structured' | 'markdown'>('llm_structured');
  const [loading, setLoading] = useState(false);
  const [responseMd, setResponseMd] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [similarityTopK, setSimilarityTopK] = useState<number>(3);
  const [citationChunkSize, setCitationChunkSize] = useState<number>(512);

  const onSubmit = async () => {
    setLoading(true);
    setError(null);
    setResponseMd(null);
    try {
      const endpoint = indexChoice === 'llm_structured' ? '/api/query/llm_structured' : '/api/query/markdown';
      const url = `${endpoint}?q=${encodeURIComponent(query)}&similarity_top_k=${encodeURIComponent(String(similarityTopK))}&citation_chunk_size=${encodeURIComponent(String(citationChunkSize))}`;
      const res = await fetch(url, { method: 'GET' });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed with ${res.status}`);
      }
      const data = await res.json();
      const citations = (data.citations || []) as Array<{ source: string; text: string }>; 
      const citationsMd = citations.length
        ? citations.map((c) => `- **${c.source}**\n\n${c.text}`).join('\n\n')
        : 'No citations available.';
      const md = `**Answer**\n\n${data.response}\n\n**Citations**\n\n${citationsMd}`;
      setResponseMd(md);
    } catch (e: any) {
      setError(e?.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <HeaderNav signOut={() => {}} />
      <Flex direction="column" gap={6} p={6} maxW="900px" mx="auto">
        <Text fontSize="2xl" fontWeight="bold">Legal Query</Text>
        <Box>
          <Text fontSize="sm" color="gray.700" mb={2}>Sample queries</Text>
          <HStack flexWrap="wrap" gap={2}>
            {sampleQueries.slice(0, 8).map((q) => (
              <Button key={q} size="sm" variant="outline" onClick={() => setQuery(q)}>{q}</Button>
            ))}
          </HStack>
        </Box>
        <RadioGroup onChange={(v) => setIndexChoice(v as any)} value={indexChoice}>
          <HStack spacing={6}>
            <Radio value="llm_structured">LLM Structured</Radio>
            <Radio value="markdown">Markdown</Radio>
          </HStack>
        </RadioGroup>
        <Textarea
          placeholder="Ask about the laws..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={4}
        />
        <HStack>
          <Box>
            <Text fontSize="sm" mb={1}>Similarity Top K</Text>
            <NumberInput min={1} max={20} value={similarityTopK} onChange={(_, n) => setSimilarityTopK(Number.isNaN(n) ? 3 : n)}>
              <NumberInputField />
            </NumberInput>
          </Box>
          <Box>
            <Text fontSize="sm" mb={1}>Citation Chunk Size</Text>
            <NumberInput min={64} max={4000} step={64} value={citationChunkSize} onChange={(_, n) => setCitationChunkSize(Number.isNaN(n) ? 512 : n)}>
              <NumberInputField />
            </NumberInput>
          </Box>
        </HStack>
        <Button colorScheme="blue" onClick={onSubmit} isLoading={loading} isDisabled={!query.trim()} width="fit-content">
          Ask
        </Button>
        {error && (
          <Box color="red.600" bg="red.50" border="1px solid" borderColor="red.200" p={4} borderRadius="md">
            {error}
          </Box>
        )}
        {responseMd && (
          <Box p={4} border="1px solid #DBDCE1" borderRadius="md" bg="white">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{responseMd}</ReactMarkdown>
          </Box>
        )}
        <Box fontSize="sm" color="gray.600">
          Backend endpoints via proxy: <code>/api/query/llm_structured</code>, <code>/api/query/markdown</code>
        </Box>
      </Flex>
    </>
  );
}
