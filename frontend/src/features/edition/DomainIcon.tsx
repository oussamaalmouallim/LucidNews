import type { LucideProps } from 'lucide-react'
import { createElement } from 'react'
import { domainIcon } from './domains'

/** The icon of a domain (a generic one for a category without its own). */
export function DomainIcon({ domain, ...props }: { domain: string } & LucideProps) {
  return createElement(domainIcon(domain), props)
}
