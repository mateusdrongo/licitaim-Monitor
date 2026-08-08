import type { QueryKey, UseMutationOptions, UseMutationResult, UseQueryOptions, UseQueryResult } from '@tanstack/react-query';
import type { AiSearchInput, AiSearchResult, Alerta, AlertaCount, AlertaPage, ApiError, ConviteInput, Dashboard, Documento, DocumentoInput, DocumentoPage, DocumentoPncp, DocumentoUpdate, Favorito, FavoritoInput, FavoritoPage, GetHistoricoPrecosParams, HealthStatus, HistoricoPrecos, ItemLicitacao, Licitacao, LicitacaoDetalhe, LicitacaoPage, ListAlertasParams, ListDocumentosParams, ListFavoritosParams, ListLicitacoesParams, ListOportunidadesParams, MembroEquipe, MembroUpdate, Monitoramento, MonitoramentoInput, MonitoramentoUpdate, Oportunidade, OportunidadeInput, OportunidadeUpdate, PipelineStat, SuccessMessage, User, UserProfileUpdate } from './api.schemas';
import { customFetch } from '../custom-fetch';
import type { ErrorType, BodyType } from '../custom-fetch';
type AwaitedInput<T> = PromiseLike<T> | T;
type Awaited<O> = O extends AwaitedInput<infer T> ? T : never;
type SecondParameter<T extends (...args: never) => unknown> = Parameters<T>[1];
export declare const getHealthCheckUrl: () => string;
/**
 * Returns server health status
 * @summary Health check
 */
export declare const healthCheck: (options?: RequestInit) => Promise<HealthStatus>;
export declare const getHealthCheckQueryKey: () => readonly ["/api/healthz"];
export declare const getHealthCheckQueryOptions: <TData = Awaited<ReturnType<typeof healthCheck>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData> & {
    queryKey: QueryKey;
};
export type HealthCheckQueryResult = NonNullable<Awaited<ReturnType<typeof healthCheck>>>;
export type HealthCheckQueryError = ErrorType<unknown>;
/**
 * @summary Health check
 */
export declare function useHealthCheck<TData = Awaited<ReturnType<typeof healthCheck>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof healthCheck>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getGetMeUrl: () => string;
/**
 * @summary Get current authenticated user
 */
export declare const getMe: (options?: RequestInit) => Promise<User>;
export declare const getGetMeQueryKey: () => readonly ["/api/auth/me"];
export declare const getGetMeQueryOptions: <TData = Awaited<ReturnType<typeof getMe>>, TError = ErrorType<ApiError>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getMe>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getMe>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetMeQueryResult = NonNullable<Awaited<ReturnType<typeof getMe>>>;
export type GetMeQueryError = ErrorType<ApiError>;
/**
 * @summary Get current authenticated user
 */
export declare function useGetMe<TData = Awaited<ReturnType<typeof getMe>>, TError = ErrorType<ApiError>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getMe>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
/**
 * @summary Update notification preferences for the current user
 */
export declare const patchMe: (userProfileUpdate: BodyType<UserProfileUpdate>, options?: RequestInit) => Promise<User>;
export declare const getPatchMeMutationOptions: <TError = ErrorType<ApiError>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof patchMe>>, TError, {
        data: BodyType<UserProfileUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof patchMe>>, TError, {
    data: BodyType<UserProfileUpdate>;
}, TContext>;
export type PatchMeMutationResult = NonNullable<Awaited<ReturnType<typeof patchMe>>>;
export type PatchMeMutationBody = BodyType<UserProfileUpdate>;
export type PatchMeMutationError = ErrorType<ApiError>;
/**
 * @summary Update notification preferences for the current user
 */
export declare const usePatchMe: <TError = ErrorType<ApiError>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof patchMe>>, TError, {
        data: BodyType<UserProfileUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof patchMe>>, TError, {
    data: BodyType<UserProfileUpdate>;
}, TContext>;
export declare const getLogoutUrl: () => string;
/**
 * @summary Logout current session
 */
export declare const logout: (options?: RequestInit) => Promise<SuccessMessage>;
export declare const getLogoutMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof logout>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof logout>>, TError, void, TContext>;
export type LogoutMutationResult = NonNullable<Awaited<ReturnType<typeof logout>>>;
export type LogoutMutationError = ErrorType<unknown>;
/**
* @summary Logout current session
*/
export declare const useLogout: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof logout>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof logout>>, TError, void, TContext>;
export declare const getGetDashboardUrl: () => string;
/**
 * @summary Get dashboard overview stats
 */
export declare const getDashboard: (options?: RequestInit) => Promise<Dashboard>;
export declare const getGetDashboardQueryKey: () => readonly ["/api/dashboard"];
export declare const getGetDashboardQueryOptions: <TData = Awaited<ReturnType<typeof getDashboard>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDashboard>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getDashboard>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetDashboardQueryResult = NonNullable<Awaited<ReturnType<typeof getDashboard>>>;
export type GetDashboardQueryError = ErrorType<unknown>;
/**
 * @summary Get dashboard overview stats
 */
export declare function useGetDashboard<TData = Awaited<ReturnType<typeof getDashboard>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDashboard>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getListLicitacoesUrl: (params?: ListLicitacoesParams) => string;
/**
 * @summary Pesquisar e listar licitações públicas
 */
export declare const listLicitacoes: (params?: ListLicitacoesParams, options?: RequestInit) => Promise<LicitacaoPage>;
export declare const getListLicitacoesQueryKey: (params?: ListLicitacoesParams) => readonly ["/api/licitacoes", ...ListLicitacoesParams[]];
export declare const getListLicitacoesQueryOptions: <TData = Awaited<ReturnType<typeof listLicitacoes>>, TError = ErrorType<unknown>>(params?: ListLicitacoesParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listLicitacoes>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listLicitacoes>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListLicitacoesQueryResult = NonNullable<Awaited<ReturnType<typeof listLicitacoes>>>;
export type ListLicitacoesQueryError = ErrorType<unknown>;
/**
 * @summary Pesquisar e listar licitações públicas
 */
export declare function useListLicitacoes<TData = Awaited<ReturnType<typeof listLicitacoes>>, TError = ErrorType<unknown>>(params?: ListLicitacoesParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listLicitacoes>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getGetLicitacaoUrl: (id: string) => string;
/**
 * @summary Detalhes de uma licitação
 */
export declare const getLicitacao: (id: string, options?: RequestInit) => Promise<LicitacaoDetalhe>;
export declare const getGetLicitacaoQueryKey: (id: string) => readonly [`/api/licitacoes/${string}`];
export declare const getGetLicitacaoQueryOptions: <TData = Awaited<ReturnType<typeof getLicitacao>>, TError = ErrorType<ApiError>>(id: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getLicitacao>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getLicitacao>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetLicitacaoQueryResult = NonNullable<Awaited<ReturnType<typeof getLicitacao>>>;
export type GetLicitacaoQueryError = ErrorType<ApiError>;
/**
 * @summary Detalhes de uma licitação
 */
export declare function useGetLicitacao<TData = Awaited<ReturnType<typeof getLicitacao>>, TError = ErrorType<ApiError>>(id: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getLicitacao>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getGetLicitacaoItensUrl: (id: string) => string;
/**
 * @summary Itens de uma licitação
 */
export declare const getLicitacaoItens: (id: string, options?: RequestInit) => Promise<ItemLicitacao[]>;
export declare const getGetLicitacaoItensQueryKey: (id: string) => readonly [`/api/licitacoes/${string}/itens`];
export declare const getGetLicitacaoItensQueryOptions: <TData = Awaited<ReturnType<typeof getLicitacaoItens>>, TError = ErrorType<unknown>>(id: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getLicitacaoItens>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getLicitacaoItens>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetLicitacaoItensQueryResult = NonNullable<Awaited<ReturnType<typeof getLicitacaoItens>>>;
export type GetLicitacaoItensQueryError = ErrorType<unknown>;
/**
 * @summary Itens de uma licitação
 */
export declare function useGetLicitacaoItens<TData = Awaited<ReturnType<typeof getLicitacaoItens>>, TError = ErrorType<unknown>>(id: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getLicitacaoItens>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getGetLicitacaoDocumentosPncpUrl: (id: string) => string;
/**
 * @summary Documentos públicos da licitação no PNCP
 */
export declare const getLicitacaoDocumentosPncp: (id: string, options?: RequestInit) => Promise<DocumentoPncp[]>;
export declare const getGetLicitacaoDocumentosPncpQueryKey: (id: string) => readonly [`/api/licitacoes/${string}/documentos-pncp`];
export declare const getGetLicitacaoDocumentosPncpQueryOptions: <TData = Awaited<ReturnType<typeof getLicitacaoDocumentosPncp>>, TError = ErrorType<unknown>>(id: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getLicitacaoDocumentosPncp>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getLicitacaoDocumentosPncp>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetLicitacaoDocumentosPncpQueryResult = NonNullable<Awaited<ReturnType<typeof getLicitacaoDocumentosPncp>>>;
export type GetLicitacaoDocumentosPncpQueryError = ErrorType<unknown>;
/**
 * @summary Documentos públicos da licitação no PNCP
 */
export declare function useGetLicitacaoDocumentosPncp<TData = Awaited<ReturnType<typeof getLicitacaoDocumentosPncp>>, TError = ErrorType<unknown>>(id: string, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getLicitacaoDocumentosPncp>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getListFavoritosUrl: (params?: ListFavoritosParams) => string;
/**
 * @summary Listar licitações favoritadas
 */
export declare const listFavoritos: (params?: ListFavoritosParams, options?: RequestInit) => Promise<FavoritoPage>;
export declare const getListFavoritosQueryKey: (params?: ListFavoritosParams) => readonly ["/api/favoritos", ...ListFavoritosParams[]];
export declare const getListFavoritosQueryOptions: <TData = Awaited<ReturnType<typeof listFavoritos>>, TError = ErrorType<unknown>>(params?: ListFavoritosParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listFavoritos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listFavoritos>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListFavoritosQueryResult = NonNullable<Awaited<ReturnType<typeof listFavoritos>>>;
export type ListFavoritosQueryError = ErrorType<unknown>;
/**
 * @summary Listar licitações favoritadas
 */
export declare function useListFavoritos<TData = Awaited<ReturnType<typeof listFavoritos>>, TError = ErrorType<unknown>>(params?: ListFavoritosParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listFavoritos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getCreateFavoritoUrl: () => string;
/**
 * @summary Favoritar uma licitação
 */
export declare const createFavorito: (favoritoInput: FavoritoInput, options?: RequestInit) => Promise<Favorito>;
export declare const getCreateFavoritoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createFavorito>>, TError, {
        data: BodyType<FavoritoInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof createFavorito>>, TError, {
    data: BodyType<FavoritoInput>;
}, TContext>;
export type CreateFavoritoMutationResult = NonNullable<Awaited<ReturnType<typeof createFavorito>>>;
export type CreateFavoritoMutationBody = BodyType<FavoritoInput>;
export type CreateFavoritoMutationError = ErrorType<unknown>;
/**
* @summary Favoritar uma licitação
*/
export declare const useCreateFavorito: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createFavorito>>, TError, {
        data: BodyType<FavoritoInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof createFavorito>>, TError, {
    data: BodyType<FavoritoInput>;
}, TContext>;
export declare const getDeleteFavoritoUrl: (id: number) => string;
/**
 * @summary Remover favorito
 */
export declare const deleteFavorito: (id: number, options?: RequestInit) => Promise<SuccessMessage>;
export declare const getDeleteFavoritoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteFavorito>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof deleteFavorito>>, TError, {
    id: number;
}, TContext>;
export type DeleteFavoritoMutationResult = NonNullable<Awaited<ReturnType<typeof deleteFavorito>>>;
export type DeleteFavoritoMutationError = ErrorType<unknown>;
/**
* @summary Remover favorito
*/
export declare const useDeleteFavorito: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteFavorito>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof deleteFavorito>>, TError, {
    id: number;
}, TContext>;
export declare const getListMonitoramentosUrl: () => string;
/**
 * @summary Listar monitoramentos configurados
 */
export declare const listMonitoramentos: (options?: RequestInit) => Promise<Monitoramento[]>;
export declare const getListMonitoramentosQueryKey: () => readonly ["/api/monitoramentos"];
export declare const getListMonitoramentosQueryOptions: <TData = Awaited<ReturnType<typeof listMonitoramentos>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listMonitoramentos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listMonitoramentos>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListMonitoramentosQueryResult = NonNullable<Awaited<ReturnType<typeof listMonitoramentos>>>;
export type ListMonitoramentosQueryError = ErrorType<unknown>;
/**
 * @summary Listar monitoramentos configurados
 */
export declare function useListMonitoramentos<TData = Awaited<ReturnType<typeof listMonitoramentos>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listMonitoramentos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getCreateMonitoramentoUrl: () => string;
/**
 * @summary Criar novo monitoramento automático
 */
export declare const createMonitoramento: (monitoramentoInput: MonitoramentoInput, options?: RequestInit) => Promise<Monitoramento>;
export declare const getCreateMonitoramentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createMonitoramento>>, TError, {
        data: BodyType<MonitoramentoInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof createMonitoramento>>, TError, {
    data: BodyType<MonitoramentoInput>;
}, TContext>;
export type CreateMonitoramentoMutationResult = NonNullable<Awaited<ReturnType<typeof createMonitoramento>>>;
export type CreateMonitoramentoMutationBody = BodyType<MonitoramentoInput>;
export type CreateMonitoramentoMutationError = ErrorType<unknown>;
/**
* @summary Criar novo monitoramento automático
*/
export declare const useCreateMonitoramento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createMonitoramento>>, TError, {
        data: BodyType<MonitoramentoInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof createMonitoramento>>, TError, {
    data: BodyType<MonitoramentoInput>;
}, TContext>;
export declare const getGetMonitoramentoUrl: (id: number) => string;
/**
 * @summary Detalhes de um monitoramento
 */
export declare const getMonitoramento: (id: number, options?: RequestInit) => Promise<Monitoramento>;
export declare const getGetMonitoramentoQueryKey: (id: number) => readonly [`/api/monitoramentos/${number}`];
export declare const getGetMonitoramentoQueryOptions: <TData = Awaited<ReturnType<typeof getMonitoramento>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getMonitoramento>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getMonitoramento>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetMonitoramentoQueryResult = NonNullable<Awaited<ReturnType<typeof getMonitoramento>>>;
export type GetMonitoramentoQueryError = ErrorType<unknown>;
/**
 * @summary Detalhes de um monitoramento
 */
export declare function useGetMonitoramento<TData = Awaited<ReturnType<typeof getMonitoramento>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getMonitoramento>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getUpdateMonitoramentoUrl: (id: number) => string;
/**
 * @summary Atualizar monitoramento
 */
export declare const updateMonitoramento: (id: number, monitoramentoUpdate: MonitoramentoUpdate, options?: RequestInit) => Promise<Monitoramento>;
export declare const getUpdateMonitoramentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateMonitoramento>>, TError, {
        id: number;
        data: BodyType<MonitoramentoUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateMonitoramento>>, TError, {
    id: number;
    data: BodyType<MonitoramentoUpdate>;
}, TContext>;
export type UpdateMonitoramentoMutationResult = NonNullable<Awaited<ReturnType<typeof updateMonitoramento>>>;
export type UpdateMonitoramentoMutationBody = BodyType<MonitoramentoUpdate>;
export type UpdateMonitoramentoMutationError = ErrorType<unknown>;
/**
* @summary Atualizar monitoramento
*/
export declare const useUpdateMonitoramento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateMonitoramento>>, TError, {
        id: number;
        data: BodyType<MonitoramentoUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateMonitoramento>>, TError, {
    id: number;
    data: BodyType<MonitoramentoUpdate>;
}, TContext>;
export declare const getDeleteMonitoramentoUrl: (id: number) => string;
/**
 * @summary Excluir monitoramento
 */
export declare const deleteMonitoramento: (id: number, options?: RequestInit) => Promise<SuccessMessage>;
export declare const getDeleteMonitoramentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteMonitoramento>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof deleteMonitoramento>>, TError, {
    id: number;
}, TContext>;
export type DeleteMonitoramentoMutationResult = NonNullable<Awaited<ReturnType<typeof deleteMonitoramento>>>;
export type DeleteMonitoramentoMutationError = ErrorType<unknown>;
/**
* @summary Excluir monitoramento
*/
export declare const useDeleteMonitoramento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteMonitoramento>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof deleteMonitoramento>>, TError, {
    id: number;
}, TContext>;
export declare const getToggleMonitoramentoUrl: (id: number) => string;
/**
 * @summary Ativar/desativar monitoramento
 */
export declare const toggleMonitoramento: (id: number, options?: RequestInit) => Promise<Monitoramento>;
export declare const getToggleMonitoramentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof toggleMonitoramento>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof toggleMonitoramento>>, TError, {
    id: number;
}, TContext>;
export type ToggleMonitoramentoMutationResult = NonNullable<Awaited<ReturnType<typeof toggleMonitoramento>>>;
export type ToggleMonitoramentoMutationError = ErrorType<unknown>;
/**
* @summary Ativar/desativar monitoramento
*/
export declare const useToggleMonitoramento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof toggleMonitoramento>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof toggleMonitoramento>>, TError, {
    id: number;
}, TContext>;
export declare const getListAlertasUrl: (params?: ListAlertasParams) => string;
/**
 * @summary Listar alertas do usuário
 */
export declare const listAlertas: (params?: ListAlertasParams, options?: RequestInit) => Promise<AlertaPage>;
export declare const getListAlertasQueryKey: (params?: ListAlertasParams) => readonly ["/api/alertas", ...ListAlertasParams[]];
export declare const getListAlertasQueryOptions: <TData = Awaited<ReturnType<typeof listAlertas>>, TError = ErrorType<unknown>>(params?: ListAlertasParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listAlertas>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listAlertas>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListAlertasQueryResult = NonNullable<Awaited<ReturnType<typeof listAlertas>>>;
export type ListAlertasQueryError = ErrorType<unknown>;
/**
 * @summary Listar alertas do usuário
 */
export declare function useListAlertas<TData = Awaited<ReturnType<typeof listAlertas>>, TError = ErrorType<unknown>>(params?: ListAlertasParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listAlertas>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getCountAlertasNaoLidosUrl: () => string;
/**
 * @summary Contar alertas não lidos
 */
export declare const countAlertasNaoLidos: (options?: RequestInit) => Promise<AlertaCount>;
export declare const getCountAlertasNaoLidosQueryKey: () => readonly ["/api/alertas/nao-lidos"];
export declare const getCountAlertasNaoLidosQueryOptions: <TData = Awaited<ReturnType<typeof countAlertasNaoLidos>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof countAlertasNaoLidos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof countAlertasNaoLidos>>, TError, TData> & {
    queryKey: QueryKey;
};
export type CountAlertasNaoLidosQueryResult = NonNullable<Awaited<ReturnType<typeof countAlertasNaoLidos>>>;
export type CountAlertasNaoLidosQueryError = ErrorType<unknown>;
/**
 * @summary Contar alertas não lidos
 */
export declare function useCountAlertasNaoLidos<TData = Awaited<ReturnType<typeof countAlertasNaoLidos>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof countAlertasNaoLidos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getMarcarAlertaLidoUrl: (id: number) => string;
/**
 * @summary Marcar alerta como lido
 */
export declare const marcarAlertaLido: (id: number, options?: RequestInit) => Promise<Alerta>;
export declare const getMarcarAlertaLidoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof marcarAlertaLido>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof marcarAlertaLido>>, TError, {
    id: number;
}, TContext>;
export type MarcarAlertaLidoMutationResult = NonNullable<Awaited<ReturnType<typeof marcarAlertaLido>>>;
export type MarcarAlertaLidoMutationError = ErrorType<unknown>;
/**
* @summary Marcar alerta como lido
*/
export declare const useMarcarAlertaLido: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof marcarAlertaLido>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof marcarAlertaLido>>, TError, {
    id: number;
}, TContext>;
export declare const getMarcarTodosAlertasLidosUrl: () => string;
/**
 * @summary Marcar todos alertas como lidos
 */
export declare const marcarTodosAlertasLidos: (options?: RequestInit) => Promise<SuccessMessage>;
export declare const getMarcarTodosAlertasLidosMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof marcarTodosAlertasLidos>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof marcarTodosAlertasLidos>>, TError, void, TContext>;
export type MarcarTodosAlertasLidosMutationResult = NonNullable<Awaited<ReturnType<typeof marcarTodosAlertasLidos>>>;
export type MarcarTodosAlertasLidosMutationError = ErrorType<unknown>;
/**
* @summary Marcar todos alertas como lidos
*/
export declare const useMarcarTodosAlertasLidos: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof marcarTodosAlertasLidos>>, TError, void, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof marcarTodosAlertasLidos>>, TError, void, TContext>;
export declare const getListDocumentosUrl: (params?: ListDocumentosParams) => string;
/**
 * @summary Listar documentos do usuário
 */
export declare const listDocumentos: (params?: ListDocumentosParams, options?: RequestInit) => Promise<DocumentoPage>;
export declare const getListDocumentosQueryKey: (params?: ListDocumentosParams) => readonly ["/api/documentos", ...ListDocumentosParams[]];
export declare const getListDocumentosQueryOptions: <TData = Awaited<ReturnType<typeof listDocumentos>>, TError = ErrorType<unknown>>(params?: ListDocumentosParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listDocumentos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listDocumentos>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListDocumentosQueryResult = NonNullable<Awaited<ReturnType<typeof listDocumentos>>>;
export type ListDocumentosQueryError = ErrorType<unknown>;
/**
 * @summary Listar documentos do usuário
 */
export declare function useListDocumentos<TData = Awaited<ReturnType<typeof listDocumentos>>, TError = ErrorType<unknown>>(params?: ListDocumentosParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listDocumentos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getCreateDocumentoUrl: () => string;
/**
 * @summary Criar registro de documento
 */
export declare const createDocumento: (documentoInput: DocumentoInput, options?: RequestInit) => Promise<Documento>;
export declare const getCreateDocumentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createDocumento>>, TError, {
        data: BodyType<DocumentoInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof createDocumento>>, TError, {
    data: BodyType<DocumentoInput>;
}, TContext>;
export type CreateDocumentoMutationResult = NonNullable<Awaited<ReturnType<typeof createDocumento>>>;
export type CreateDocumentoMutationBody = BodyType<DocumentoInput>;
export type CreateDocumentoMutationError = ErrorType<unknown>;
/**
* @summary Criar registro de documento
*/
export declare const useCreateDocumento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createDocumento>>, TError, {
        data: BodyType<DocumentoInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof createDocumento>>, TError, {
    data: BodyType<DocumentoInput>;
}, TContext>;
export declare const getGetDocumentoUrl: (id: number) => string;
/**
 * @summary Detalhes de um documento
 */
export declare const getDocumento: (id: number, options?: RequestInit) => Promise<Documento>;
export declare const getGetDocumentoQueryKey: (id: number) => readonly [`/api/documentos/${number}`];
export declare const getGetDocumentoQueryOptions: <TData = Awaited<ReturnType<typeof getDocumento>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDocumento>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getDocumento>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetDocumentoQueryResult = NonNullable<Awaited<ReturnType<typeof getDocumento>>>;
export type GetDocumentoQueryError = ErrorType<unknown>;
/**
 * @summary Detalhes de um documento
 */
export declare function useGetDocumento<TData = Awaited<ReturnType<typeof getDocumento>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDocumento>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getUpdateDocumentoUrl: (id: number) => string;
/**
 * @summary Atualizar documento
 */
export declare const updateDocumento: (id: number, documentoUpdate: DocumentoUpdate, options?: RequestInit) => Promise<Documento>;
export declare const getUpdateDocumentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateDocumento>>, TError, {
        id: number;
        data: BodyType<DocumentoUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateDocumento>>, TError, {
    id: number;
    data: BodyType<DocumentoUpdate>;
}, TContext>;
export type UpdateDocumentoMutationResult = NonNullable<Awaited<ReturnType<typeof updateDocumento>>>;
export type UpdateDocumentoMutationBody = BodyType<DocumentoUpdate>;
export type UpdateDocumentoMutationError = ErrorType<unknown>;
/**
* @summary Atualizar documento
*/
export declare const useUpdateDocumento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateDocumento>>, TError, {
        id: number;
        data: BodyType<DocumentoUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateDocumento>>, TError, {
    id: number;
    data: BodyType<DocumentoUpdate>;
}, TContext>;
export declare const getDeleteDocumentoUrl: (id: number) => string;
/**
 * @summary Excluir documento
 */
export declare const deleteDocumento: (id: number, options?: RequestInit) => Promise<SuccessMessage>;
export declare const getDeleteDocumentoMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteDocumento>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof deleteDocumento>>, TError, {
    id: number;
}, TContext>;
export type DeleteDocumentoMutationResult = NonNullable<Awaited<ReturnType<typeof deleteDocumento>>>;
export type DeleteDocumentoMutationError = ErrorType<unknown>;
/**
* @summary Excluir documento
*/
export declare const useDeleteDocumento: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteDocumento>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof deleteDocumento>>, TError, {
    id: number;
}, TContext>;
export declare const getGetEquipeUrl: () => string;
/**
 * @summary Listar membros da equipe
 */
export declare const getEquipe: (options?: RequestInit) => Promise<MembroEquipe[]>;
export declare const getGetEquipeQueryKey: () => readonly ["/api/equipe"];
export declare const getGetEquipeQueryOptions: <TData = Awaited<ReturnType<typeof getEquipe>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getEquipe>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getEquipe>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetEquipeQueryResult = NonNullable<Awaited<ReturnType<typeof getEquipe>>>;
export type GetEquipeQueryError = ErrorType<unknown>;
/**
 * @summary Listar membros da equipe
 */
export declare function useGetEquipe<TData = Awaited<ReturnType<typeof getEquipe>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getEquipe>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getConvidarMembroUrl: () => string;
/**
 * @summary Convidar membro para a equipe
 */
export declare const convidarMembro: (conviteInput: ConviteInput, options?: RequestInit) => Promise<MembroEquipe>;
export declare const getConvidarMembroMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof convidarMembro>>, TError, {
        data: BodyType<ConviteInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof convidarMembro>>, TError, {
    data: BodyType<ConviteInput>;
}, TContext>;
export type ConvidarMembroMutationResult = NonNullable<Awaited<ReturnType<typeof convidarMembro>>>;
export type ConvidarMembroMutationBody = BodyType<ConviteInput>;
export type ConvidarMembroMutationError = ErrorType<unknown>;
/**
* @summary Convidar membro para a equipe
*/
export declare const useConvidarMembro: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof convidarMembro>>, TError, {
        data: BodyType<ConviteInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof convidarMembro>>, TError, {
    data: BodyType<ConviteInput>;
}, TContext>;
export declare const getUpdateMembroUrl: (id: number) => string;
/**
 * @summary Atualizar permissões do membro
 */
export declare const updateMembro: (id: number, membroUpdate: MembroUpdate, options?: RequestInit) => Promise<MembroEquipe>;
export declare const getUpdateMembroMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateMembro>>, TError, {
        id: number;
        data: BodyType<MembroUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateMembro>>, TError, {
    id: number;
    data: BodyType<MembroUpdate>;
}, TContext>;
export type UpdateMembroMutationResult = NonNullable<Awaited<ReturnType<typeof updateMembro>>>;
export type UpdateMembroMutationBody = BodyType<MembroUpdate>;
export type UpdateMembroMutationError = ErrorType<unknown>;
/**
* @summary Atualizar permissões do membro
*/
export declare const useUpdateMembro: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateMembro>>, TError, {
        id: number;
        data: BodyType<MembroUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateMembro>>, TError, {
    id: number;
    data: BodyType<MembroUpdate>;
}, TContext>;
export declare const getRemoverMembroUrl: (id: number) => string;
/**
 * @summary Remover membro da equipe
 */
export declare const removerMembro: (id: number, options?: RequestInit) => Promise<SuccessMessage>;
export declare const getRemoverMembroMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof removerMembro>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof removerMembro>>, TError, {
    id: number;
}, TContext>;
export type RemoverMembroMutationResult = NonNullable<Awaited<ReturnType<typeof removerMembro>>>;
export type RemoverMembroMutationError = ErrorType<unknown>;
/**
* @summary Remover membro da equipe
*/
export declare const useRemoverMembro: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof removerMembro>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof removerMembro>>, TError, {
    id: number;
}, TContext>;
export declare const getListOportunidadesUrl: (params?: ListOportunidadesParams) => string;
/**
 * @summary Listar oportunidades no pipeline
 */
export declare const listOportunidades: (params?: ListOportunidadesParams, options?: RequestInit) => Promise<Oportunidade[]>;
export declare const getListOportunidadesQueryKey: (params?: ListOportunidadesParams) => readonly ["/api/oportunidades", ...ListOportunidadesParams[]];
export declare const getListOportunidadesQueryOptions: <TData = Awaited<ReturnType<typeof listOportunidades>>, TError = ErrorType<unknown>>(params?: ListOportunidadesParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listOportunidades>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof listOportunidades>>, TError, TData> & {
    queryKey: QueryKey;
};
export type ListOportunidadesQueryResult = NonNullable<Awaited<ReturnType<typeof listOportunidades>>>;
export type ListOportunidadesQueryError = ErrorType<unknown>;
/**
 * @summary Listar oportunidades no pipeline
 */
export declare function useListOportunidades<TData = Awaited<ReturnType<typeof listOportunidades>>, TError = ErrorType<unknown>>(params?: ListOportunidadesParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof listOportunidades>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getCreateOportunidadeUrl: () => string;
/**
 * @summary Adicionar oportunidade ao pipeline
 */
export declare const createOportunidade: (oportunidadeInput: OportunidadeInput, options?: RequestInit) => Promise<Oportunidade>;
export declare const getCreateOportunidadeMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createOportunidade>>, TError, {
        data: BodyType<OportunidadeInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof createOportunidade>>, TError, {
    data: BodyType<OportunidadeInput>;
}, TContext>;
export type CreateOportunidadeMutationResult = NonNullable<Awaited<ReturnType<typeof createOportunidade>>>;
export type CreateOportunidadeMutationBody = BodyType<OportunidadeInput>;
export type CreateOportunidadeMutationError = ErrorType<unknown>;
/**
* @summary Adicionar oportunidade ao pipeline
*/
export declare const useCreateOportunidade: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof createOportunidade>>, TError, {
        data: BodyType<OportunidadeInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof createOportunidade>>, TError, {
    data: BodyType<OportunidadeInput>;
}, TContext>;
export declare const getGetOportunidadeUrl: (id: number) => string;
/**
 * @summary Detalhes de uma oportunidade
 */
export declare const getOportunidade: (id: number, options?: RequestInit) => Promise<Oportunidade>;
export declare const getGetOportunidadeQueryKey: (id: number) => readonly [`/api/oportunidades/${number}`];
export declare const getGetOportunidadeQueryOptions: <TData = Awaited<ReturnType<typeof getOportunidade>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getOportunidade>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getOportunidade>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetOportunidadeQueryResult = NonNullable<Awaited<ReturnType<typeof getOportunidade>>>;
export type GetOportunidadeQueryError = ErrorType<unknown>;
/**
 * @summary Detalhes de uma oportunidade
 */
export declare function useGetOportunidade<TData = Awaited<ReturnType<typeof getOportunidade>>, TError = ErrorType<unknown>>(id: number, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getOportunidade>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getUpdateOportunidadeUrl: (id: number) => string;
/**
 * @summary Atualizar oportunidade
 */
export declare const updateOportunidade: (id: number, oportunidadeUpdate: OportunidadeUpdate, options?: RequestInit) => Promise<Oportunidade>;
export declare const getUpdateOportunidadeMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateOportunidade>>, TError, {
        id: number;
        data: BodyType<OportunidadeUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof updateOportunidade>>, TError, {
    id: number;
    data: BodyType<OportunidadeUpdate>;
}, TContext>;
export type UpdateOportunidadeMutationResult = NonNullable<Awaited<ReturnType<typeof updateOportunidade>>>;
export type UpdateOportunidadeMutationBody = BodyType<OportunidadeUpdate>;
export type UpdateOportunidadeMutationError = ErrorType<unknown>;
/**
* @summary Atualizar oportunidade
*/
export declare const useUpdateOportunidade: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof updateOportunidade>>, TError, {
        id: number;
        data: BodyType<OportunidadeUpdate>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof updateOportunidade>>, TError, {
    id: number;
    data: BodyType<OportunidadeUpdate>;
}, TContext>;
export declare const getDeleteOportunidadeUrl: (id: number) => string;
/**
 * @summary Remover oportunidade
 */
export declare const deleteOportunidade: (id: number, options?: RequestInit) => Promise<SuccessMessage>;
export declare const getDeleteOportunidadeMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteOportunidade>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof deleteOportunidade>>, TError, {
    id: number;
}, TContext>;
export type DeleteOportunidadeMutationResult = NonNullable<Awaited<ReturnType<typeof deleteOportunidade>>>;
export type DeleteOportunidadeMutationError = ErrorType<unknown>;
/**
* @summary Remover oportunidade
*/
export declare const useDeleteOportunidade: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof deleteOportunidade>>, TError, {
        id: number;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof deleteOportunidade>>, TError, {
    id: number;
}, TContext>;
export declare const getGetPipelineStatsUrl: () => string;
/**
 * @summary Estatísticas do pipeline por estágio
 */
export declare const getPipelineStats: (options?: RequestInit) => Promise<PipelineStat[]>;
export declare const getGetPipelineStatsQueryKey: () => readonly ["/api/oportunidades/pipeline-stats"];
export declare const getGetPipelineStatsQueryOptions: <TData = Awaited<ReturnType<typeof getPipelineStats>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getPipelineStats>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getPipelineStats>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetPipelineStatsQueryResult = NonNullable<Awaited<ReturnType<typeof getPipelineStats>>>;
export type GetPipelineStatsQueryError = ErrorType<unknown>;
/**
 * @summary Estatísticas do pipeline por estágio
 */
export declare function useGetPipelineStats<TData = Awaited<ReturnType<typeof getPipelineStats>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getPipelineStats>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getGetHistoricoPrecosUrl: (params: GetHistoricoPrecosParams) => string;
/**
 * @summary Consultar histórico de preços por item/descrição
 */
export declare const getHistoricoPrecos: (params: GetHistoricoPrecosParams, options?: RequestInit) => Promise<HistoricoPrecos>;
export declare const getGetHistoricoPrecosQueryKey: (params?: GetHistoricoPrecosParams) => readonly ["/api/precos/historico", ...GetHistoricoPrecosParams[]];
export declare const getGetHistoricoPrecosQueryOptions: <TData = Awaited<ReturnType<typeof getHistoricoPrecos>>, TError = ErrorType<unknown>>(params: GetHistoricoPrecosParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getHistoricoPrecos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getHistoricoPrecos>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetHistoricoPrecosQueryResult = NonNullable<Awaited<ReturnType<typeof getHistoricoPrecos>>>;
export type GetHistoricoPrecosQueryError = ErrorType<unknown>;
/**
 * @summary Consultar histórico de preços por item/descrição
 */
export declare function useGetHistoricoPrecos<TData = Awaited<ReturnType<typeof getHistoricoPrecos>>, TError = ErrorType<unknown>>(params: GetHistoricoPrecosParams, options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getHistoricoPrecos>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export declare const getAiSearchUrl: () => string;
/**
 * @summary Pesquisa inteligente com IA
 */
export declare const aiSearch: (aiSearchInput: AiSearchInput, options?: RequestInit) => Promise<AiSearchResult>;
export declare const getAiSearchMutationOptions: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof aiSearch>>, TError, {
        data: BodyType<AiSearchInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationOptions<Awaited<ReturnType<typeof aiSearch>>, TError, {
    data: BodyType<AiSearchInput>;
}, TContext>;
export type AiSearchMutationResult = NonNullable<Awaited<ReturnType<typeof aiSearch>>>;
export type AiSearchMutationBody = BodyType<AiSearchInput>;
export type AiSearchMutationError = ErrorType<unknown>;
/**
* @summary Pesquisa inteligente com IA
*/
export declare const useAiSearch: <TError = ErrorType<unknown>, TContext = unknown>(options?: {
    mutation?: UseMutationOptions<Awaited<ReturnType<typeof aiSearch>>, TError, {
        data: BodyType<AiSearchInput>;
    }, TContext>;
    request?: SecondParameter<typeof customFetch>;
}) => UseMutationResult<Awaited<ReturnType<typeof aiSearch>>, TError, {
    data: BodyType<AiSearchInput>;
}, TContext>;
export declare const getGetAiSugestoesUrl: () => string;
/**
 * @summary Sugestões de licitações baseadas no perfil do usuário
 */
export declare const getAiSugestoes: (options?: RequestInit) => Promise<Licitacao[]>;
export declare const getGetAiSugestoesQueryKey: () => readonly ["/api/ai/sugestoes"];
export declare const getGetAiSugestoesQueryOptions: <TData = Awaited<ReturnType<typeof getAiSugestoes>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getAiSugestoes>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}) => UseQueryOptions<Awaited<ReturnType<typeof getAiSugestoes>>, TError, TData> & {
    queryKey: QueryKey;
};
export type GetAiSugestoesQueryResult = NonNullable<Awaited<ReturnType<typeof getAiSugestoes>>>;
export type GetAiSugestoesQueryError = ErrorType<unknown>;
/**
 * @summary Sugestões de licitações baseadas no perfil do usuário
 */
export declare function useGetAiSugestoes<TData = Awaited<ReturnType<typeof getAiSugestoes>>, TError = ErrorType<unknown>>(options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getAiSugestoes>>, TError, TData>;
    request?: SecondParameter<typeof customFetch>;
}): UseQueryResult<TData, TError> & {
    queryKey: QueryKey;
};
export {};
//# sourceMappingURL=api.d.ts.map