import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { decodeEmbeddedUrls, RequirementText } from './requirement-text';

describe('RequirementText', () => {
  it('decodes mixed percent-encoded URLs without failing on malformed fragments', () => {
    const value =
      '获取资料：http://czj.xz.gov.cn/Home/HomeIndex%EF%BC%89/%E2%80%9D%EF%BC%88附件）以及 mailto:%E6%8B%9B%E6%A0%87@example.com。';

    expect(decodeEmbeddedUrls(value)).toContain('HomeIndex）/”');
    expect(decodeEmbeddedUrls(value)).toContain('mailto:招标@example.com');
  });

  it('renders decoded web and mail links as links', () => {
    render(
      <RequirementText value='详情见 http://example.com/%E6%8B%9B%E6%A0%87 或 mailto:%E6%8B%9B%E6%A0%87@example.com。' />
    );

    expect(screen.getByRole('link', { name: 'http://example.com/招标' })).toHaveAttribute(
      'href',
      'http://example.com/招标'
    );
    expect(screen.getByRole('link', { name: 'mailto:招标@example.com' })).toHaveAttribute(
      'href',
      'mailto:招标@example.com'
    );
  });
});
