import { useDataQuery } from '@dhis2/app-runtime'
import { useState, useEffect, useCallback } from 'react'
import type { FacilityRecord, SyncStats } from '@/types'

const OSID_ATTR_CODE = 'SUNBIRD_OSID'

interface UseFacilityOrgUnitsResult {
    records: FacilityRecord[]
    loading: boolean
    error: Error | null
    stats: SyncStats
    refetch: () => void
}

// Query for OSID attribute ID
const osidAttrQuery = {
    osidAttr: {
        resource: 'attributes',
        params: {
            filter: `code:eq:${OSID_ATTR_CODE}`,
            fields: 'id',
        },
    },
}

export const useFacilityOrgUnits = (
    orgUnitGroupIds: string[],
    statusFilter: 'all' | 'pending' | 'synced' = 'all'
): UseFacilityOrgUnitsResult => {
    const [records, setRecords] = useState<FacilityRecord[]>([])
    const [stats, setStats] = useState<SyncStats>({ total: 0, synced: 0, pending: 0 })
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<Error | null>(null)

    // Get OSID attribute ID
    const {
        data: osidData,
        loading: osidLoading,
        error: osidError,
        engine,
    } = useDataQuery<{
        osidAttr: { attributes: Array<{ id: string }> }
    }>(osidAttrQuery)

    const osidAttrId = osidData?.osidAttr?.attributes?.[0]?.id

    const fetchOrgUnits = useCallback(async () => {
        if (!engine || orgUnitGroupIds.length === 0) {
            setRecords([])
            setStats({ total: 0, synced: 0, pending: 0 })
            return
        }

        setLoading(true)
        setError(null)

        try {
            // Build filter for org unit groups
            const groupFilter = orgUnitGroupIds.join(',')

            const result = await engine.query({
                orgUnits: {
                    resource: 'organisationUnits',
                    params: {
                        filter: `organisationUnitGroups.id:in:[${groupFilter}]`,
                        fields: 'id,name,code,shortName,geometry,ancestors[id,name,level],attributeValues[attribute[id,code],value]',
                        paging: false,
                    },
                },
            })

            const orgUnits = (result.orgUnits as any).organisationUnits || []

            // Transform to FacilityRecord
            const transformed: FacilityRecord[] = orgUnits.map((ou: any) => {
                // Get OSID if exists
                let osid: string | undefined
                for (const av of ou.attributeValues || []) {
                    if (av.attribute?.code === OSID_ATTR_CODE || av.attribute?.id === osidAttrId) {
                        osid = av.value
                        break
                    }
                }

                // Build location string from ancestors
                const ancestors = ou.ancestors || []
                const locationParts: string[] = []

                // Sort ancestors by level and get names
                const sortedAncestors = [...ancestors].sort((a: any, b: any) => a.level - b.level)
                for (const ancestor of sortedAncestors) {
                    if (ancestor.level >= 2) { // Skip country level
                        locationParts.push(ancestor.name)
                    }
                }
                const location = locationParts.join(' > ')

                // Get coordinates if available
                let coordinates: { lon: number; lat: number } | undefined
                if (ou.geometry?.type === 'Point' && ou.geometry.coordinates?.length >= 2) {
                    coordinates = {
                        lon: ou.geometry.coordinates[0],
                        lat: ou.geometry.coordinates[1],
                    }
                }

                return {
                    id: ou.id,
                    name: ou.name,
                    code: ou.code || '',
                    location,
                    coordinates,
                    syncStatus: osid ? 'synced' : 'pending',
                    osid,
                } as FacilityRecord
            })

            // Calculate stats
            const syncedCount = transformed.filter((r) => r.syncStatus === 'synced').length
            const pendingCount = transformed.filter((r) => r.syncStatus === 'pending').length

            setStats({
                total: transformed.length,
                synced: syncedCount,
                pending: pendingCount,
            })

            // Apply status filter
            let filtered = transformed
            if (statusFilter === 'pending') {
                filtered = transformed.filter((r) => r.syncStatus === 'pending')
            } else if (statusFilter === 'synced') {
                filtered = transformed.filter((r) => r.syncStatus === 'synced')
            }

            setRecords(filtered)
        } catch (err) {
            setError(err instanceof Error ? err : new Error('Failed to fetch org units'))
        } finally {
            setLoading(false)
        }
    }, [engine, orgUnitGroupIds, osidAttrId, statusFilter])

    // Fetch when dependencies change
    useEffect(() => {
        if (!osidLoading && orgUnitGroupIds.length > 0) {
            fetchOrgUnits()
        }
    }, [osidLoading, orgUnitGroupIds.join(','), statusFilter])

    return {
        records,
        loading: osidLoading || loading,
        error: osidError || error || null,
        stats,
        refetch: fetchOrgUnits,
    }
}
