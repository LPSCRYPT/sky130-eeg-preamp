-- The PDF is a standalone anonymous attachment, not a local filesystem browser.
function Link(link)
  if link.target:match('^https?://') or link.target:match('^#') then return link end
  return link.content
end
