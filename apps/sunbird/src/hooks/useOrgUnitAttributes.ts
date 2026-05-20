import { useDataQuery } from '@dhis2/app-runtime'

export interface OrgUnitAttribute {
    id: string
    displayName: string
    code: string
}

const query = {
    attributes: {
        resource: 'attributes',
        params: {
            filter: 'organisationUnitAttribute:eq:true',
            fields: 'id,displayName,code',
            paging: false,
        },
    },
}

interface QueryResult {
    attributes: {
        attributes: Array<{
            id: string
            displayName: string
            code: string
        }>
    }
}

interface UseOrgUnitAttributesResult {
    attributes: OrgUnitAttribute[]
    loading: boolean
    error: Error | null
}

export const useOrgUnitAttributes = (): UseOrgUnitAttributesResult => {
    const { data, loading, error } = useDataQuery<QueryResult>(query)

    const attributes: OrgUnitAttribute[] = (data?.attributes?.attributes || []).map(
        (attr) => ({
            id: attr.id,
            displayName: attr.displayName,
            code: attr.code || '',
        })
    )

    return {
        attributes,
        loading,
        error: error || null,
    }
}
