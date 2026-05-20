import { useState, useCallback } from 'react'

interface SchemaField {
    path: string
    label: string
    type: string
    required: boolean
}

interface UseSunbirdSchemaResult {
    fields: SchemaField[]
    loading: boolean
    error: string | null
    fetchSchema: (sunbirdUrl: string, entityType: string) => Promise<void>
    clearSchema: () => void
}

/**
 * Extract base URL from Sunbird API URL
 * e.g., "http://localhost:8081/api/v1" -> "http://localhost:8081"
 */
function extractBaseUrl(apiUrl: string): string {
    try {
        const url = new URL(apiUrl)
        return `${url.protocol}//${url.host}`
    } catch {
        // If URL parsing fails, try to extract manually
        const match = apiUrl.match(/^(https?:\/\/[^\/]+)/)
        return match ? match[1] : apiUrl
    }
}

/**
 * Recursively extract field paths from JSON schema
 */
function extractFieldsFromSchema(
    schema: any,
    prefix: string = '',
    requiredFields: string[] = []
): SchemaField[] {
    const fields: SchemaField[] = []

    if (!schema || !schema.properties) {
        return fields
    }

    for (const [key, value] of Object.entries(schema.properties) as [string, any][]) {
        const path = prefix ? `${prefix}.${key}` : key
        const isRequired = requiredFields.includes(key)

        // Skip system fields
        if (['osid', 'osCreatedAt', 'osUpdatedAt', 'osCreatedBy', 'osUpdatedBy'].includes(key)) {
            continue
        }

        if (value.type === 'object' && value.properties) {
            // Nested object - recurse
            const nestedRequired = value.required || []
            fields.push(...extractFieldsFromSchema(value, path, nestedRequired))
        } else if (value.type === 'array' && value.items?.type === 'object') {
            // Array of objects - add the array path and recurse for item fields
            fields.push({
                path: `${path}[]`,
                label: `${path} (array)`,
                type: 'array',
                required: isRequired,
            })
            const itemRequired = value.items.required || []
            const itemFields = extractFieldsFromSchema(value.items, `${path}[]`, itemRequired)
            fields.push(...itemFields)
        } else {
            // Simple field
            fields.push({
                path,
                label: path,
                type: value.type || 'string',
                required: isRequired,
            })
        }
    }

    return fields
}

export const useSunbirdSchema = (): UseSunbirdSchemaResult => {
    const [fields, setFields] = useState<SchemaField[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchSchema = useCallback(async (sunbirdUrl: string, entityType: string) => {
        if (!sunbirdUrl || !entityType) {
            setError('Sunbird URL and Entity Type are required')
            return
        }

        setLoading(true)
        setError(null)
        setFields([])

        try {
            const baseUrl = extractBaseUrl(sunbirdUrl)
            const schemaUrl = `${baseUrl}/api/docs/${entityType}.json`

            console.log('Fetching schema from:', schemaUrl)

            const response = await fetch(schemaUrl)

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error(`Entity type "${entityType}" not found in Sunbird RC`)
                }
                throw new Error(`Failed to fetch schema: ${response.status} ${response.statusText}`)
            }

            const schema = await response.json()

            // The schema structure is: { EntityType: { $ref: "#/definitions/EntityType" }, definitions: { EntityType: {...} } }
            const entitySchema = schema.definitions?.[entityType] || schema[entityType]

            if (!entitySchema) {
                throw new Error(`Schema for "${entityType}" not found in response`)
            }

            const requiredFields = entitySchema.required || []
            const extractedFields = extractFieldsFromSchema(entitySchema, '', requiredFields)

            // Sort: required fields first, then alphabetically
            extractedFields.sort((a, b) => {
                if (a.required && !b.required) return -1
                if (!a.required && b.required) return 1
                return a.path.localeCompare(b.path)
            })

            setFields(extractedFields)
            console.log('Extracted fields:', extractedFields)

        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to fetch schema'
            setError(message)
            console.error('Schema fetch error:', err)
        } finally {
            setLoading(false)
        }
    }, [])

    const clearSchema = useCallback(() => {
        setFields([])
        setError(null)
    }, [])

    return {
        fields,
        loading,
        error,
        fetchSchema,
        clearSchema,
    }
}

export type { SchemaField }
